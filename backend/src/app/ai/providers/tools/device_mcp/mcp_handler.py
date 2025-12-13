"""Mô-đun hỗ trợ client MCP phía thiết bị"""

from __future__ import annotations
import json
import asyncio
import re
from concurrent.futures import Future
from typing import TYPE_CHECKING
from app.ai.utils.util import get_vision_url, sanitize_tool_name
from app.ai.utils.auth import AuthToken
from app.core.logger import setup_logging

if TYPE_CHECKING:
    from app.ai.connection import (
        ConnectionHandler,
    )  # chỉ dùng cho hint, không chạy lúc runtime

TAG = __name__
logger = setup_logging()


class MCPClient:
    """Client MCP phía thiết bị để quản lý trạng thái và công cụ"""

    def __init__(self):
        self.tools = {}  # sanitized_name -> tool_data
        self.name_mapping = {}
        self.ready = False
        self.call_results = {}  # To store Futures for tool call responses
        self.next_id = 1
        self.lock = asyncio.Lock()
        self._cached_available_tools = None  # Cache for get_available_tools

    def has_tool(self, name: str) -> bool:
        return name in self.tools

    def get_available_tools(self) -> list:
        # Check if the cache is valid
        if self._cached_available_tools is not None:
            return self._cached_available_tools

        # If cache is not valid, regenerate the list
        result = []
        for tool_name, tool_data in self.tools.items():
            function_def = {
                "name": tool_name,
                "description": tool_data["description"],
                "parameters": {
                    "type": tool_data["inputSchema"].get("type", "object"),
                    "properties": tool_data["inputSchema"].get("properties", {}),
                    "required": tool_data["inputSchema"].get("required", []),
                },
            }
            result.append({"type": "function", "function": function_def})

        self._cached_available_tools = result  # Store the generated list in cache
        return result

    async def is_ready(self) -> bool:
        async with self.lock:
            return self.ready

    async def set_ready(self, status: bool):
        async with self.lock:
            self.ready = status

    async def add_tool(self, tool_data: dict):
        async with self.lock:
            sanitized_name = sanitize_tool_name(tool_data["name"])
            self.tools[sanitized_name] = tool_data
            self.name_mapping[sanitized_name] = tool_data["name"]
            self._cached_available_tools = (
                None  # Invalidate the cache when a tool is added
            )

    async def get_next_id(self) -> int:
        async with self.lock:
            current_id = self.next_id
            self.next_id += 1
            return current_id

    async def register_call_result_future(self, id: int, future: Future):
        async with self.lock:
            self.call_results[id] = future

    async def resolve_call_result(self, id: int, result: any):
        async with self.lock:
            if id in self.call_results:
                future = self.call_results.pop(id)
                if not future.done():
                    future.set_result(result)

    async def reject_call_result(self, id: int, exception: Exception):
        async with self.lock:
            if id in self.call_results:
                future = self.call_results.pop(id)
                if not future.done():
                    future.set_exception(exception)

    async def cleanup_call_result(self, id: int):
        async with self.lock:
            if id in self.call_results:
                self.call_results.pop(id)


async def send_mcp_message(conn: ConnectionHandler, payload: dict):
    """Hàm trợ giúp gửi thông điệp MCP, đóng gói logic dùng chung."""
    if not conn.features.get("mcp"):
        logger.bind(tag=TAG).warning(
            "Client không hỗ trợ MCP, không thể gửi thông điệp MCP"
        )
        return

    message = json.dumps({"type": "mcp", "payload": payload})

    try:
        await conn.send_raw(message)
        logger.bind(tag=TAG).debug(f"Gửi thông điệp MCP thành công: {message}")
    except Exception as e:
        logger.bind(tag=TAG).error(f"Gửi thông điệp MCP thất bại: {e}")


async def handle_mcp_message(
    conn: ConnectionHandler, mcp_client: MCPClient, payload: dict
):
    """Xử lý thông điệp MCP gồm khởi tạo, danh sách công cụ và phản hồi lời gọi"""
    logger.bind(tag=TAG).debug(f"Đang xử lý thông điệp MCP: {str(payload)[:100]}")

    if not isinstance(payload, dict):
        logger.bind(tag=TAG).error(
            "Thông điệp MCP thiếu trường payload hoặc sai định dạng"
        )
        return

    # Handle result
    if "result" in payload:
        result = payload["result"]
        msg_id = int(payload.get("id", 0))

        # Check for tool call response first
        if msg_id in mcp_client.call_results:
            logger.bind(tag=TAG).debug(
                f"Nhận phản hồi gọi công cụ, ID: {msg_id}, kết quả: {result}"
            )
            await mcp_client.resolve_call_result(msg_id, result)
            return

        if msg_id == 1:  # mcpInitializeID
            logger.bind(tag=TAG).debug("Nhận phản hồi khởi tạo MCP")
            server_info = result.get("serverInfo")
            if isinstance(server_info, dict):
                name = server_info.get("name")
                version = server_info.get("version")
                logger.bind(tag=TAG).debug(
                    f"Thông tin máy chủ MCP phía client: name={name}, version={version}"
                )
            return

        elif msg_id == 2:  # mcpToolsListID
            logger.bind(tag=TAG).debug("Nhận phản hồi danh sách công cụ MCP")
            if isinstance(result, dict) and "tools" in result:
                tools_data = result["tools"]
                if not isinstance(tools_data, list):
                    logger.bind(tag=TAG).error("Danh sách công cụ sai định dạng")
                    return

                logger.bind(tag=TAG).debug(
                    f"Số lượng công cụ thiết bị client hỗ trợ: {len(tools_data)}"
                )

                for i, tool in enumerate(tools_data):
                    if not isinstance(tool, dict):
                        continue

                    name = tool.get("name", "")
                    description = tool.get("description", "")
                    input_schema = {"type": "object", "properties": {}, "required": []}

                    if "inputSchema" in tool and isinstance(tool["inputSchema"], dict):
                        schema = tool["inputSchema"]
                        input_schema["type"] = schema.get("type", "object")
                        input_schema["properties"] = schema.get("properties", {})
                        input_schema["required"] = [
                            s for s in schema.get("required", []) if isinstance(s, str)
                        ]

                    new_tool = {
                        "name": name,
                        "description": description,
                        "inputSchema": input_schema,
                    }
                    await mcp_client.add_tool(new_tool)
                    logger.bind(tag=TAG).debug(f"Công cụ client #{i+1}: {name}")

                # Thay thế mọi tên công cụ trong mô tả bằng tên đã chuẩn hóa
                for tool_data in mcp_client.tools.values():
                    if "description" in tool_data:
                        description = tool_data["description"]
                        # Duyệt qua toàn bộ tên công cụ để thay thế
                        for (
                            sanitized_name,
                            original_name,
                        ) in mcp_client.name_mapping.items():
                            description = description.replace(
                                original_name, sanitized_name
                            )
                        tool_data["description"] = description

                next_cursor = result.get("nextCursor", "")
                if next_cursor:
                    logger.bind(tag=TAG).info(
                        f"Còn công cụ khác, nextCursor: {next_cursor}"
                    )
                    await send_mcp_tools_list_continue_request(conn, next_cursor)
                else:
                    await mcp_client.set_ready(True)
                    logger.bind(tag=TAG).debug(
                        "Đã nhận toàn bộ công cụ, client MCP sẵn sàng"
                    )

                    # Làm mới bộ nhớ đệm công cụ để đưa MCP vào danh sách hàm
                    if hasattr(conn, "func_handler") and conn.func_handler:
                        conn.func_handler.tool_manager.refresh_tools()
                        conn.func_handler.current_support_functions()
            return

    # Handle method calls (requests from the client)
    elif "method" in payload:
        method = payload["method"]
        logger.bind(tag=TAG).info(f"Nhận yêu cầu từ client MCP: {method}")

    elif "error" in payload:
        error_data = payload["error"]
        error_msg = error_data.get("message", "Lỗi không xác định")
        logger.bind(tag=TAG).error(f"Nhận phản hồi lỗi MCP: {error_msg}")

        msg_id = int(payload.get("id", 0))
        if msg_id in mcp_client.call_results:
            await mcp_client.reject_call_result(
                msg_id, Exception(f"Lỗi MCP: {error_msg}")
            )


async def send_mcp_initialize_message(conn):
    """Gửi thông điệp khởi tạo MCP"""

    vision_url = get_vision_url(conn.config)

    # Sinh token từ khóa bí mật
    auth = AuthToken(conn.config["server"]["auth_key"])
    token = auth.generate_token(conn.headers.get("device-id"))

    vision = {
        "url": vision_url,
        "token": token,
    }

    payload = {
        "jsonrpc": "2.0",
        "id": 1,  # mcpInitializeID
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {
                "roots": {"listChanged": True},
                "sampling": {},
                "vision": vision,
            },
            "clientInfo": {
                "name": "XiaozhiClient",
                "version": "1.0.0",
            },
        },
    }
    logger.bind(tag=TAG).debug("Gửi thông điệp khởi tạo MCP")
    await send_mcp_message(conn, payload)


async def send_mcp_tools_list_request(conn: ConnectionHandler):
    """Gửi yêu cầu danh sách công cụ MCP"""
    payload = {
        "jsonrpc": "2.0",
        "id": 2,  # mcpToolsListID
        "method": "tools/list",
    }
    logger.bind(tag=TAG).debug("Gửi yêu cầu danh sách công cụ MCP")
    await send_mcp_message(conn, payload)


async def send_mcp_tools_list_continue_request(conn: ConnectionHandler, cursor: str):
    """Gửi yêu cầu danh sách công cụ MCP kèm cursor"""
    payload = {
        "jsonrpc": "2.0",
        "id": 2,  # mcpToolsListID (same ID for continuation)
        "method": "tools/list",
        "params": {"cursor": cursor},
    }
    logger.bind(tag=TAG).info(f"Gửi yêu cầu danh sách công cụ MCP với cursor: {cursor}")
    await send_mcp_message(conn, payload)


async def call_mcp_tool(
    conn: ConnectionHandler,
    mcp_client: MCPClient,
    tool_name: str,
    args: str = "{}",
    timeout: int = 30,
):
    """
    Gọi công cụ cụ thể và chờ phản hồi
    """
    if not await mcp_client.is_ready():
        raise RuntimeError("Client MCP chưa sẵn sàng")

    if not mcp_client.has_tool(tool_name):
        raise ValueError(f"Công cụ {tool_name} không tồn tại")

    tool_call_id = await mcp_client.get_next_id()
    result_future = asyncio.Future()
    await mcp_client.register_call_result_future(tool_call_id, result_future)

    # Xử lý tham số
    try:
        if isinstance(args, str):
            # Đảm bảo chuỗi là JSON hợp lệ
            if not args.strip():
                arguments = {}
            else:
                try:
                    # Cố gắng phân tích trực tiếp
                    arguments = json.loads(args)
                except json.JSONDecodeError:
                    # Nếu thất bại, thử gộp nhiều đối tượng JSON
                    try:
                        # Dùng regex để tìm mọi đối tượng JSON
                        json_objects = re.findall(r"\{[^{}]*\}", args)
                        if len(json_objects) > 1:
                            # Hợp nhất các đối tượng JSON
                            merged_dict = {}
                            for json_str in json_objects:
                                try:
                                    obj = json.loads(json_str)
                                    if isinstance(obj, dict):
                                        merged_dict.update(obj)
                                except json.JSONDecodeError:
                                    continue
                            if merged_dict:
                                arguments = merged_dict
                            else:
                                raise ValueError(
                                    f"Không thể phân tích JSON hợp lệ nào: {args}"
                                )
                        else:
                            raise ValueError(f"Phân tích JSON tham số thất bại: {args}")
                    except Exception as e:
                        logger.bind(tag=TAG).error(
                            f"Phân tích JSON tham số thất bại: {str(e)}, tham số gốc: {args}"
                        )
                        raise ValueError(f"Phân tích JSON tham số thất bại: {str(e)}")
        elif isinstance(args, dict):
            arguments = args
        else:
            raise ValueError(
                f"Sai kiểu tham số, mong đợi chuỗi hoặc dict, nhận: {type(args)}"
            )

        # Đảm bảo tham số là dict
        if not isinstance(arguments, dict):
            raise ValueError(f"Tham số phải là dict, nhận: {type(arguments)}")

    except Exception as e:
        if not isinstance(e, ValueError):
            raise ValueError(f"Xử lý tham số thất bại: {str(e)}")
        raise e

    actual_name = mcp_client.name_mapping.get(tool_name, tool_name)
    payload = {
        "jsonrpc": "2.0",
        "id": tool_call_id,
        "method": "tools/call",
        "params": {"name": actual_name, "arguments": arguments},
    }

    logger.bind(tag=TAG).info(
        f"Gửi yêu cầu gọi công cụ MCP client: {actual_name}, tham số: {args}"
    )
    await send_mcp_message(conn, payload)

    try:
        # Chờ phản hồi hoặc hết thời gian
        raw_result = await asyncio.wait_for(result_future, timeout=timeout)
        logger.bind(tag=TAG).info(
            f"Client MCP gọi công cụ {actual_name} thành công, kết quả gốc: {raw_result}"
        )

        if isinstance(raw_result, dict):
            if raw_result.get("isError") is True:
                error_msg = raw_result.get(
                    "error",
                    "Lời gọi công cụ trả về lỗi nhưng không có thông tin chi tiết",
                )
                raise RuntimeError(f"Lỗi khi gọi công cụ: {error_msg}")

            content = raw_result.get("content")
            if isinstance(content, list) and len(content) > 0:
                if isinstance(content[0], dict) and "text" in content[0]:
                    # Trả về nội dung văn bản trực tiếp, không phân tích JSON
                    return content[0]["text"]
        # Nếu kết quả không đúng định dạng mong đợi, chuyển thành chuỗi
        return str(raw_result)
    except asyncio.TimeoutError:
        await mcp_client.cleanup_call_result(tool_call_id)
        raise TimeoutError("Yêu cầu gọi công cụ quá thời gian chờ")
    except Exception as e:
        await mcp_client.cleanup_call_result(tool_call_id)
        raise e
