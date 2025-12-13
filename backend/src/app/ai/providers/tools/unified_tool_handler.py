"""Bộ xử lý công cụ hợp nhất"""

from __future__ import annotations
import json
from typing import TYPE_CHECKING, Dict, List, Any, Optional
from app.core.logger import setup_logging
from app.ai.plugins_func.loadplugins import auto_import_modules

from .base import ToolType
from app.ai.plugins_func.register import Action, ActionResponse
from .unified_tool_manager import ToolManager
from .server_plugins import ServerPluginExecutor
from .server_mcp import ServerMCPExecutor
from .device_iot import DeviceIoTExecutor
from .device_mcp import DeviceMCPExecutor
from .mcp_endpoint import MCPEndpointExecutor

if TYPE_CHECKING:
    from app.ai.connection import (
        ConnectionHandler,
    )  # chỉ dùng cho hint, không chạy lúc runtime


class UnifiedToolHandler:
    """Bộ xử lý công cụ hợp nhất"""

    def __init__(self, conn: ConnectionHandler, tool_refs: list[str] | None = None):
        """
        Khởi tạo UnifiedToolHandler.

        Args:
            conn: Connection handler
            tool_refs: Danh sách tool references từ agent config (optional).
                      Nếu None, sẽ fallback về config["Intent"]["functions"]
        """
        self.conn = conn
        self.config = conn.config
        self.logger = setup_logging()
        self._tool_refs = tool_refs

        # Tạo trình quản lý công cụ
        self.tool_manager = ToolManager(conn)

        # Tạo các bộ thực thi cho từng loại
        # Truyền tool_refs cho ServerPluginExecutor
        self.server_plugin_executor = ServerPluginExecutor(conn, tool_refs=tool_refs)
        self.server_mcp_executor = ServerMCPExecutor(conn)
        self.device_iot_executor = DeviceIoTExecutor(conn)
        self.device_mcp_executor = DeviceMCPExecutor(conn)
        self.mcp_endpoint_executor = MCPEndpointExecutor(conn)

        # Đăng ký bộ thực thi
        self.tool_manager.register_executor(
            ToolType.SERVER_PLUGIN, self.server_plugin_executor
        )
        self.tool_manager.register_executor(
            ToolType.SERVER_MCP, self.server_mcp_executor
        )
        self.tool_manager.register_executor(
            ToolType.DEVICE_IOT, self.device_iot_executor
        )
        self.tool_manager.register_executor(
            ToolType.DEVICE_MCP, self.device_mcp_executor
        )
        self.tool_manager.register_executor(
            ToolType.MCP_ENDPOINT, self.mcp_endpoint_executor
        )

        # Cờ đánh dấu khởi tạo
        self.finish_init = False

    async def _initialize(self):
        """Khởi tạo bất đồng bộ"""
        try:
            # Tự động nhập các mô-đun plugin
            auto_import_modules("app.ai.plugins_func.functions")

            # Khởi tạo MCP phía máy chủ
            await self.server_mcp_executor.initialize()

            # Khởi tạo điểm kết nối MCP
            await self._initialize_mcp_endpoint()

            # Khởi tạo Home Assistant (nếu cần)
            # self._initialize_home_assistant()

            self.finish_init = True
            self.logger.debug("Khởi tạo bộ xử lý công cụ hợp nhất hoàn tất")

            # Xuất danh sách các công cụ đang được hỗ trợ
            self.current_support_functions()

        except Exception as e:
            self.logger.error(f"Khởi tạo bộ xử lý công cụ hợp nhất thất bại: {e}")

    async def _initialize_mcp_endpoint(self):
        """Khởi tạo điểm kết nối MCP"""
        try:
            from .mcp_endpoint import connect_mcp_endpoint

            # Lấy URL điểm kết nối MCP từ cấu hình
            mcp_endpoint_url = self.config.get("mcp_endpoint", "")

            if (
                mcp_endpoint_url
                and "你的" not in mcp_endpoint_url
                and mcp_endpoint_url != "null"
            ):
                self.logger.info(f"Đang khởi tạo điểm kết nối MCP: {mcp_endpoint_url}")
                mcp_endpoint_client = await connect_mcp_endpoint(
                    mcp_endpoint_url, self.conn
                )

                if mcp_endpoint_client:
                    # Lưu client điểm kết nối MCP vào đối tượng kết nối
                    self.conn.mcp_endpoint_client = mcp_endpoint_client
                    self.logger.info("Khởi tạo điểm kết nối MCP thành công")
                else:
                    self.logger.warning("Khởi tạo điểm kết nối MCP thất bại")

        except Exception as e:
            self.logger.error(f"Khởi tạo điểm kết nối MCP thất bại: {e}")

    def _initialize_home_assistant(self):
        """Khởi tạo prompt Home Assistant"""
        try:
            from app.ai.plugins_func.functions.hass_init import append_devices_to_prompt

            append_devices_to_prompt(self.conn)
        except ImportError:
            pass  # Bỏ qua lỗi nhập khẩu
        except Exception as e:
            self.logger.error(f"Khởi tạo Home Assistant thất bại: {e}")

    def get_functions(self) -> List[Dict[str, Any]]:
        """Lấy mô tả hàm của tất cả công cụ"""
        return self.tool_manager.get_function_descriptions()

    def current_support_functions(self) -> List[str]:
        """Lấy danh sách tên hàm đang được hỗ trợ"""
        func_names = self.tool_manager.get_supported_tool_names()
        self.logger.debug(f"Danh sách hàm đang được hỗ trợ: {func_names}")
        return func_names

    def upload_functions_desc(self):
        """Làm mới danh sách mô tả hàm"""
        self.tool_manager.refresh_tools()
        self.logger.info("Danh sách mô tả hàm đã được làm mới")

    def has_tool(self, tool_name: str) -> bool:
        """Kiểm tra xem công cụ có tồn tại hay không"""
        return self.tool_manager.has_tool(tool_name)

    async def handle_llm_function_call(
        self, conn, function_call_data: Dict[str, Any]
    ) -> Optional[ActionResponse]:
        """Xử lý lời gọi hàm từ LLM"""
        try:
            # Xử lý trường hợp gọi nhiều hàm
            if "function_calls" in function_call_data:
                responses = []
                for call in function_call_data["function_calls"]:
                    result = await self.tool_manager.execute_tool(
                        call["name"], call.get("arguments") or {}
                    )
                    responses.append(result)
                return self._combine_responses(responses)

            # Xử lý trường hợp gọi một hàm
            function_name = function_call_data["name"]
            arguments = function_call_data.get("arguments") or {}

            # Nếu arguments là chuỗi, cố gắng phân tích thành JSON
            if isinstance(arguments, str):
                try:
                    arguments = json.loads(arguments) if arguments else {}
                except json.JSONDecodeError:
                    self.logger.error(f"Không thể phân tích tham số hàm: {arguments}")
                    return ActionResponse(
                        action=Action.REQLLM,
                        response="Không thể phân tích tham số hàm",
                    )

            self.logger.debug(f"Gọi hàm: {function_name}, tham số: {arguments}")

            # Thực thi lời gọi công cụ
            result = await self.tool_manager.execute_tool(function_name, arguments)
            return result

        except Exception as e:
            self.logger.error(f"Lỗi khi xử lý lời gọi hàm: {e}")
            return ActionResponse(action=Action.ERROR, response=str(e))

    def _combine_responses(self, responses: List[ActionResponse]) -> ActionResponse:
        """Gộp phản hồi của nhiều lần gọi hàm"""
        if not responses:
            return ActionResponse(action=Action.NONE, response="Không có phản hồi")

        # Nếu có lỗi, trả về lỗi đầu tiên
        for response in responses:
            if response.action == Action.ERROR:
                return response

        # Gộp các phản hồi thành công
        contents = []
        responses_text = []

        for response in responses:
            if response.content:
                contents.append(response.content)
            if response.response:
                responses_text.append(response.response)

        # Xác định loại hành động cuối cùng
        final_action = Action.RESPONSE
        for response in responses:
            if response.action == Action.REQLLM:
                final_action = Action.REQLLM
                break

        return ActionResponse(
            action=final_action,
            result="; ".join(contents) if contents else None,
            response="; ".join(responses_text) if responses_text else None,
        )

    async def register_iot_tools(self, descriptors: List[Dict[str, Any]]):
        """Đăng ký công cụ cho thiết bị IoT"""
        self.device_iot_executor.register_iot_tools(descriptors)
        self.tool_manager.refresh_tools()
        self.logger.info(f"Đã đăng ký {len(descriptors)} công cụ cho thiết bị IoT")

    def get_tool_statistics(self) -> Dict[str, int]:
        """Lấy thống kê số lượng công cụ"""
        return self.tool_manager.get_tool_statistics()

    async def cleanup(self):
        """Giải phóng tài nguyên"""
        try:
            await self.server_mcp_executor.cleanup()

            # Đóng kết nối MCP Endpoint
            if (
                hasattr(self.conn, "mcp_endpoint_client")
                and self.conn.mcp_endpoint_client
            ):
                await self.conn.mcp_endpoint_client.close()

            self.logger.debug("Hoàn tất dọn dẹp bộ xử lý công cụ")
        except Exception as e:
            self.logger.error(f"Dọn dẹp bộ xử lý công cụ thất bại: {e}")
