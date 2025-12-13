"""Bộ thực thi công cụ plugin phía máy chủ"""

from __future__ import annotations
import inspect
from typing import TYPE_CHECKING, Dict, Any
from ..base import ToolType, ToolDefinition, ToolExecutor
from app.ai.plugins_func.register import all_function_registry, Action, ActionResponse

if TYPE_CHECKING:
    from app.ai.connection import (
        ConnectionHandler,
    )  # chỉ dùng cho hint, không chạy lúc runtime


class ServerPluginExecutor(ToolExecutor):
    """Bộ thực thi công cụ plugin dành cho máy chủ"""

    def __init__(self, conn: ConnectionHandler, tool_refs: list[str] | None = None):
        """
        Khởi tạo ServerPluginExecutor.

        Args:
            conn: Connection handler
            tool_refs: Danh sách tool references từ agent config (optional).
                      Nếu None, sẽ fallback về config["Intent"]["functions"]
        """
        self.conn = conn
        self.config = conn.config
        self._tool_refs = tool_refs

    async def execute(
        self, conn: ConnectionHandler, tool_name: str, arguments: Dict[str, Any]
    ) -> ActionResponse:
        """Thực thi công cụ plugin phía máy chủ"""
        func_item = all_function_registry.get(tool_name)
        if not func_item:
            return ActionResponse(
                action=Action.NOTFOUND, response=f"Hàm plugin {tool_name} không tồn tại"
            )

        try:
            # Quyết định cách gọi dựa trên loại công cụ
            if hasattr(func_item, "type"):
                func_type = func_item.type
                if func_type.code in [4, 5]:  # SYSTEM_CTL, IOT_CTL (cần tham số conn)
                    result = func_item.func(conn, **arguments)
                elif func_type.code == 2:  # WAIT
                    result = func_item.func(**arguments)
                elif func_type.code == 3:  # CHANGE_SYS_PROMPT
                    result = func_item.func(conn, **arguments)
                else:
                    result = func_item.func(**arguments)
            else:
                # Mặc định không truyền tham số conn
                result = func_item.func(**arguments)

            if inspect.isawaitable(result):
                result = await result

            return result

        except Exception as e:
            return ActionResponse(
                action=Action.ERROR,
                response=str(e),
            )

    def get_tools(self) -> Dict[str, ToolDefinition]:
        """
        Lấy tất cả công cụ plugin phía máy chủ đã đăng ký.

        Priority:
        1. Nếu có tool_refs từ agent config → dùng đó
        2. Nếu không → fallback về config["Intent"]["functions"]
        """
        tools = {}

        # Lấy các hàm bắt buộc
        necessary_functions = ["handle_exit_intent"]

        # Xác định danh sách functions
        if self._tool_refs:
            # Dùng tool refs từ agent config
            config_functions = self._resolve_tool_names(self._tool_refs)
        else:
            # Fallback về config["Intent"]["functions"]
            config_functions = self._get_config_functions()

        # Hợp nhất các hàm cần thiết
        all_required_functions = list(set(necessary_functions + config_functions))

        for func_name in all_required_functions:
            func_item = all_function_registry.get(func_name)
            if func_item:
                tools[func_name] = ToolDefinition(
                    name=func_name,
                    description=func_item.description,
                    tool_type=ToolType.SERVER_PLUGIN,
                )

        return tools

    def _get_config_functions(self) -> list[str]:
        """Lấy danh sách hàm từ cấu hình config.yml."""
        try:
            config_functions = self.config["Intent"][
                self.config["selected_module"]["Intent"]
            ].get("functions", [])

            # Chuyển thành danh sách
            if not isinstance(config_functions, list):
                try:
                    config_functions = list(config_functions)
                except TypeError:
                    config_functions = []

            return config_functions
        except (KeyError, TypeError):
            return []

    def _resolve_tool_names(self, tool_refs: list[str]) -> list[str]:
        """
        Resolve tool references to tool names.

        Đối với:
        - UUID (UserTool): Bây giờ trả về UUID, sẽ được resolve ở execute time
          với ToolConfigResolver. Tuy nhiên, để get_tools hoạt động,
          ta cần lấy tool_name từ database hoặc skip.
        - System tool name: Trả về trực tiếp

        NOTE: Phiên bản đơn giản này chỉ xử lý system tool names.
              UserTool UUID sẽ được filter out (cần async để resolve).
        """
        tool_names = []
        for ref in tool_refs:
            # Kiểm tra nếu là UUID (36 chars, 4 dashes)
            is_uuid = len(ref) == 36 and ref.count("-") == 4

            if is_uuid:
                # Skip UserTool UUIDs trong sync context
                # TODO: Pre-resolve UserTools khi khởi tạo connection
                continue
            else:
                # System tool name
                if ref in all_function_registry:
                    tool_names.append(ref)

        return tool_names

    def has_tool(self, tool_name: str) -> bool:
        """Kiểm tra xem có công cụ plugin phía máy chủ cụ thể không"""
        return tool_name in all_function_registry
