"""Trình quản lý công cụ hợp nhất"""
from __future__ import annotations
from typing import TYPE_CHECKING, Dict, List, Optional, Any
from app.core.logger import setup_logging
from app.ai.plugins_func.register import Action, ActionResponse
from app.ai.utils.serializers import format_action_response
from .base import ToolType, ToolDefinition, ToolExecutor

if TYPE_CHECKING:
    from app.ai.connection import ConnectionHandler  # chỉ dùng cho hint, không chạy lúc runtime


class ToolManager:
    """Quản lý tập trung cho tất cả loại công cụ"""

    def __init__(self, conn: ConnectionHandler):
        self.conn = conn
        self.logger = setup_logging()
        self.executors: Dict[ToolType, ToolExecutor] = {}
        self._cached_tools: Optional[Dict[str, ToolDefinition]] = None
        self._cached_function_descriptions: Optional[List[Dict[str, Any]]] = None

    def register_executor(self, tool_type: ToolType, executor: ToolExecutor):
        """Đăng ký bộ thực thi công cụ"""
        self.executors[tool_type] = executor
        self._invalidate_cache()
        self.logger.debug(f"Đăng ký bộ thực thi cho loại công cụ: {tool_type.value}")

    def _invalidate_cache(self):
        """Vô hiệu hóa bộ nhớ đệm"""
        self._cached_tools = None
        self._cached_function_descriptions = None

    def get_all_tools(self) -> Dict[str, ToolDefinition]:
        """Lấy toàn bộ định nghĩa công cụ"""
        if self._cached_tools is not None:
            return self._cached_tools

        all_tools = {}
        for tool_type, executor in self.executors.items():
            try:
                tools = executor.get_tools()
                for name, definition in tools.items():
                    if name in all_tools:
                        self.logger.warning(f"Xung đột tên công cụ: {name}")
                    all_tools[name] = definition
            except Exception as e:
                self.logger.error(f"Lỗi khi lấy công cụ loại {tool_type.value}: {e}")

        self._cached_tools = all_tools
        return all_tools

    def get_function_descriptions(self) -> List[Dict[str, Any]]:
        """Lấy mô tả hàm của tất cả công cụ (định dạng OpenAI)"""
        if self._cached_function_descriptions is not None:
            return self._cached_function_descriptions

        descriptions = []
        tools = self.get_all_tools()
        for tool_definition in tools.values():
            descriptions.append(tool_definition.description)

        self._cached_function_descriptions = descriptions
        return descriptions

    def has_tool(self, tool_name: str) -> bool:
        """Kiểm tra sự tồn tại của công cụ"""
        tools = self.get_all_tools()
        return tool_name in tools

    def get_tool_type(self, tool_name: str) -> Optional[ToolType]:
        """Lấy loại của công cụ"""
        tools = self.get_all_tools()
        tool_def = tools.get(tool_name)
        return tool_def.tool_type if tool_def else None

    async def execute_tool(
        self, tool_name: str, arguments: Dict[str, Any]
    ) -> ActionResponse:
        """Thực thi lời gọi công cụ"""
        try:
            # Xác định loại công cụ
            tool_type = self.get_tool_type(tool_name)
            if not tool_type:
                return ActionResponse(
                    action=Action.NOTFOUND,
                    response=f"Công cụ {tool_name} không tồn tại",
                )

            # Lấy bộ thực thi tương ứng
            executor = self.executors.get(tool_type)
            if not executor:
                return ActionResponse(
                    action=Action.ERROR,
                    response=f"Chưa đăng ký bộ thực thi cho loại công cụ {tool_type.value}",
                )

            # Thực thi công cụ
            self.logger.debug(f"Thực thi công cụ: {tool_name}, tham số: {arguments}")
            result = await executor.execute(self.conn, tool_name, arguments)
            self.logger.debug(
                f"Kết quả thực thi công cụ: {format_action_response(result)}"
            )
            return result

        except Exception as e:
            self.logger.error(f"Lỗi khi thực thi công cụ {tool_name}: {e}")
            return ActionResponse(action=Action.ERROR, response=str(e))

    def get_supported_tool_names(self) -> List[str]:
        """Lấy danh sách tên công cụ được hỗ trợ"""
        tools = self.get_all_tools()
        return list(tools.keys())

    def refresh_tools(self):
        """Làm mới bộ nhớ đệm công cụ"""
        self._invalidate_cache()
        self.logger.debug("Bộ nhớ đệm công cụ đã được làm mới")

    def get_tool_statistics(self) -> Dict[str, int]:
        """Lấy thống kê số lượng công cụ"""
        stats = {}
        for tool_type, executor in self.executors.items():
            try:
                tools = executor.get_tools()
                stats[tool_type.value] = len(tools)
            except Exception as e:
                self.logger.error(
                    f"Lỗi khi lấy thống kê công cụ {tool_type.value}: {e}"
                )
                stats[tool_type.value] = 0
        return stats
