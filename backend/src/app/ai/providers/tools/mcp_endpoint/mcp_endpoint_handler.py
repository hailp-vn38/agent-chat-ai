"""Bộ xử lý điểm kết nối MCP"""

from __future__ import annotations
import json
import asyncio
import re
from typing import TYPE_CHECKING
import websockets
from app.core.logger import setup_logging
from .mcp_endpoint_client import MCPEndpointClient

if TYPE_CHECKING:
    from app.ai.connection import (
        ConnectionHandler,
    )  # chỉ dùng cho hint, không chạy lúc runtime

TAG = __name__
logger = setup_logging()


async def connect_mcp_endpoint(
    mcp_endpoint_url: str, conn: ConnectionHandler | None = None
) -> MCPEndpointClient:
    """Kết nối tới điểm MCP Endpoint"""
    if not mcp_endpoint_url or "你的" in mcp_endpoint_url or mcp_endpoint_url == "null":
        return None

    try:
        websocket = await websockets.connect(mcp_endpoint_url)

        mcp_client = MCPEndpointClient(conn)
        mcp_client.set_websocket(websocket)

        # Khởi chạy bộ lắng nghe thông điệp
        asyncio.create_task(_message_listener(mcp_client))

        # Gửi thông điệp khởi tạo
        await send_mcp_endpoint_initialize(mcp_client)

        # Gửi thông báo hoàn tất khởi tạo
        await send_mcp_endpoint_notification(mcp_client, "notifications/initialized")

        # Lấy danh sách công cụ
        await send_mcp_endpoint_tools_list(mcp_client)

        logger.bind(tag=TAG).info("Kết nối điểm MCP Endpoint thành công")
        return mcp_client

    except Exception as e:
        logger.bind(tag=TAG).error(f"Kết nối điểm MCP Endpoint thất bại: {e}")
        return None


async def _message_listener(mcp_client: MCPEndpointClient):
    """Lắng nghe thông điệp từ điểm MCP Endpoint"""
    try:
        async for message in mcp_client.websocket:
            await handle_mcp_endpoint_message(mcp_client, message)
    except websockets.exceptions.ConnectionClosed:
        logger.bind(tag=TAG).info("Kết nối điểm MCP Endpoint đã đóng")
    except Exception as e:
        logger.bind(tag=TAG).error(f"Lỗi bộ lắng nghe điểm MCP Endpoint: {e}")
    finally:
        await mcp_client.set_ready(False)


async def handle_mcp_endpoint_message(mcp_client: MCPEndpointClient, message: str):
    """Xử lý thông điệp từ điểm MCP Endpoint"""
    try:
        payload = json.loads(message)
        logger.bind(tag=TAG).debug(f"Nhận thông điệp MCP Endpoint: {payload}")

        if not isinstance(payload, dict):
            logger.bind(tag=TAG).error("Thông điệp MCP Endpoint sai định dạng")
            return

        # Handle result
        if "result" in payload:
            result = payload["result"]
            # Lấy ID thông điệp một cách an toàn, nếu None thì dùng 0
            msg_id_raw = payload.get("id")
            msg_id = int(msg_id_raw) if msg_id_raw is not None else 0

            # Check for tool call response first
            if msg_id in mcp_client.call_results:
                logger.bind(tag=TAG).debug(
                    f"Nhận phản hồi gọi công cụ, ID: {msg_id}, kết quả: {result}"
                )
                await mcp_client.resolve_call_result(msg_id, result)
                return

            if msg_id == 1:  # mcpInitializeID
                logger.bind(tag=TAG).debug("Nhận phản hồi khởi tạo MCP Endpoint")
                if result is not None and isinstance(result, dict):
                    server_info = result.get("serverInfo")
                    if isinstance(server_info, dict):
                        name = server_info.get("name")
                        version = server_info.get("version")
                        logger.bind(tag=TAG).info(
                            f"Thông tin máy chủ MCP Endpoint: name={name}, version={version}"
                        )
                else:
                    logger.bind(tag=TAG).warning(
                        "Phản hồi khởi tạo MCP Endpoint trống hoặc sai định dạng"
                    )
                return

            elif msg_id == 2:  # mcpToolsListID
                logger.bind(tag=TAG).debug(
                    "Nhận phản hồi danh sách công cụ MCP Endpoint"
                )
                if (
                    result is not None
                    and isinstance(result, dict)
                    and "tools" in result
                ):
                    tools_data = result["tools"]
                    if not isinstance(tools_data, list):
                        logger.bind(tag=TAG).error("Danh sách công cụ sai định dạng")
                        return

                    logger.bind(tag=TAG).info(
                        f"Số công cụ MCP Endpoint hỗ trợ: {len(tools_data)}"
                    )

                    for i, tool in enumerate(tools_data):
                        if not isinstance(tool, dict):
                            continue

                        name = tool.get("name", "")
                        description = tool.get("description", "")
                        input_schema = {
                            "type": "object",
                            "properties": {},
                            "required": [],
                        }

                        if "inputSchema" in tool and isinstance(
                            tool["inputSchema"], dict
                        ):
                            schema = tool["inputSchema"]
                            input_schema["type"] = schema.get("type", "object")
                            input_schema["properties"] = schema.get("properties", {})
                            input_schema["required"] = [
                                s
                                for s in schema.get("required", [])
                                if isinstance(s, str)
                            ]

                        new_tool = {
                            "name": name,
                            "description": description,
                            "inputSchema": input_schema,
                        }
                        await mcp_client.add_tool(new_tool)
                        logger.bind(tag=TAG).debug(
                            f"Công cụ MCP Endpoint #{i+1}: {name}"
                        )

                    # Thay thế mọi tên công cụ trong mô tả
                    for tool_data in mcp_client.tools.values():
                        if "description" in tool_data:
                            description = tool_data["description"]
                            # Duyệt qua tên công cụ để thay thế
                            for (
                                sanitized_name,
                                original_name,
                            ) in mcp_client.name_mapping.items():
                                description = description.replace(
                                    original_name, sanitized_name
                                )
                            tool_data["description"] = description

                    next_cursor = (
                        result.get("nextCursor", "") if result is not None else ""
                    )
                    if next_cursor:
                        logger.bind(tag=TAG).info(
                            f"Còn công cụ khác, nextCursor: {next_cursor}"
                        )
                        await send_mcp_endpoint_tools_list_continue(
                            mcp_client, next_cursor
                        )
                    else:
                        await mcp_client.set_ready(True)
                        logger.bind(tag=TAG).info(
                            "Đã lấy đủ công cụ MCP Endpoint, client sẵn sàng"
                        )

                        # Làm mới bộ nhớ đệm để thêm công cụ MCP Endpoint vào danh sách hàm
                        if (
                            hasattr(mcp_client, "conn")
                            and mcp_client.conn
                            and hasattr(mcp_client.conn, "func_handler")
                            and mcp_client.conn.func_handler
                        ):
                            mcp_client.conn.func_handler.tool_manager.refresh_tools()
                            mcp_client.conn.func_handler.current_support_functions()

                        logger.bind(tag=TAG).info(
                            f"Hoàn tất lấy công cụ MCP Endpoint, tổng {len(mcp_client.tools)} công cụ"
                        )
                else:
                    logger.bind(tag=TAG).warning(
                        "Phản hồi danh sách công cụ MCP Endpoint trống hoặc sai định dạng"
                    )
                return

        # Handle method calls (requests from the endpoint)
        elif "method" in payload:
            method = payload["method"]
            logger.bind(tag=TAG).info(f"Nhận yêu cầu từ MCP Endpoint: {method}")

        elif "error" in payload:
            error_data = payload["error"]
            error_msg = error_data.get("message", "Lỗi không xác định")
            logger.bind(tag=TAG).error(f"Nhận phản hồi lỗi MCP Endpoint: {error_msg}")

            # Lấy ID thông điệp một cách an toàn, nếu None thì dùng 0
            msg_id_raw = payload.get("id")
            msg_id = int(msg_id_raw) if msg_id_raw is not None else 0

            if msg_id in mcp_client.call_results:
                await mcp_client.reject_call_result(
                    msg_id, Exception(f"Lỗi MCP Endpoint: {error_msg}")
                )

    except json.JSONDecodeError as e:
        logger.bind(tag=TAG).error(
            f"Không thể phân tích JSON thông điệp MCP Endpoint: {e}"
        )
    except Exception as e:
        logger.bind(tag=TAG).error(f"Lỗi khi xử lý thông điệp MCP Endpoint: {e}")
        import traceback

        logger.bind(tag=TAG).error(f"Chi tiết lỗi: {traceback.format_exc()}")


async def send_mcp_endpoint_initialize(mcp_client: MCPEndpointClient):
    """Gửi thông điệp khởi tạo MCP Endpoint"""
    payload = {
        "jsonrpc": "2.0",
        "id": 1,  # mcpInitializeID
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {
                "roots": {"listChanged": True},
                "sampling": {},
            },
            "clientInfo": {
                "name": "XiaozhiMCPEndpointClient",
                "version": "1.0.0",
            },
        },
    }
    message = json.dumps(payload)
    logger.bind(tag=TAG).info("Gửi thông điệp khởi tạo MCP Endpoint")
    await mcp_client.send_message(message)


async def send_mcp_endpoint_notification(mcp_client: MCPEndpointClient, method: str):
    """Gửi thông báo tới MCP Endpoint"""
    payload = {
        "jsonrpc": "2.0",
        "method": method,
        "params": {},
    }
    message = json.dumps(payload)
    logger.bind(tag=TAG).debug(f"Gửi thông báo MCP Endpoint: {method}")
    await mcp_client.send_message(message)


async def send_mcp_endpoint_tools_list(mcp_client: MCPEndpointClient):
    """Gửi yêu cầu danh sách công cụ MCP Endpoint"""
    payload = {
        "jsonrpc": "2.0",
        "id": 2,  # mcpToolsListID
        "method": "tools/list",
    }
    message = json.dumps(payload)
    logger.bind(tag=TAG).debug("Gửi yêu cầu danh sách công cụ MCP Endpoint")
    await mcp_client.send_message(message)


async def send_mcp_endpoint_tools_list_continue(
    mcp_client: MCPEndpointClient, cursor: str
):
    """Gửi yêu cầu danh sách công cụ MCP Endpoint kèm cursor"""
    payload = {
        "jsonrpc": "2.0",
        "id": 2,  # mcpToolsListID (same ID for continuation)
        "method": "tools/list",
        "params": {"cursor": cursor},
    }
    message = json.dumps(payload)
    logger.bind(tag=TAG).info(
        f"Gửi yêu cầu danh sách công cụ MCP Endpoint với cursor: {cursor}"
    )
    await mcp_client.send_message(message)


async def call_mcp_endpoint_tool(
    mcp_client: MCPEndpointClient, tool_name: str, args: str = "{}", timeout: int = 30
):
    """
    Gọi công cụ MCP Endpoint cụ thể và chờ phản hồi
    """
    if not await mcp_client.is_ready():
        raise RuntimeError("Client MCP Endpoint chưa sẵn sàng")

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
                    # Nếu thất bại, thử hợp nhất nhiều JSON
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

    # Thêm địa chỉ MAC (dùng device_mac_address, không dùng device_id UUID)
    if mcp_client.conn and hasattr(mcp_client.conn, "device_mac_address"):
        mac_address = mcp_client.conn.device_mac_address
        if mac_address:
            arguments["mac_address"] = mac_address
            logger.bind(tag=TAG).info(
                f"Đã thêm địa chỉ MAC {mac_address} vào tham số gọi công cụ MCP Endpoint"
            )

    actual_name = mcp_client.name_mapping.get(tool_name, tool_name)
    payload = {
        "jsonrpc": "2.0",
        "id": tool_call_id,
        "method": "tools/call",
        "params": {"name": actual_name, "arguments": arguments},
    }

    message = json.dumps(payload)
    logger.bind(tag=TAG).info(
        f"Gửi yêu cầu gọi công cụ MCP Endpoint: {actual_name}, tham số: {json.dumps(arguments, ensure_ascii=False)}"
    )
    await mcp_client.send_message(message)

    try:
        # Chờ phản hồi hoặc hết thời gian
        raw_result = await asyncio.wait_for(result_future, timeout=timeout)
        logger.bind(tag=TAG).info(
            f"Gọi công cụ MCP Endpoint {actual_name} thành công, kết quả gốc: {raw_result}"
        )

        if isinstance(raw_result, dict):
            if raw_result.get("isError") is True:
                error_msg = raw_result.get(
                    "error",
                    "Lời gọi công cụ trả về lỗi nhưng không có thông tin chi tiết",
                )
                raise RuntimeError(f"Lỗi gọi công cụ: {error_msg}")

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
