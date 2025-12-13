"""Bộ thực thi công cụ MCP phía máy chủ"""
from __future__ import annotations
from typing import TYPE_CHECKING, Dict, Any, Optional
from ..base import ToolType, ToolDefinition, ToolExecutor
from app.ai.plugins_func.register import Action, ActionResponse
from .mcp_manager import ServerMCPManager
if TYPE_CHECKING:
    from app.ai.connection import ConnectionHandler  # chỉ dùng cho hint, không chạy lúc runtime


class ServerMCPExecutor(ToolExecutor):
    """Bộ thực thi công cụ MCP dành cho máy chủ"""

    def __init__(self, conn: ConnectionHandler):
        self.conn = conn
        self.mcp_manager: Optional[ServerMCPManager] = None
        self._initialized = False

    async def initialize(self):
        """Khởi tạo bộ quản lý MCP"""
        if not self._initialized:
            self.mcp_manager = ServerMCPManager(self.conn)
            self._initialized = True
            await self.mcp_manager.initialize_servers()

    async def execute(
        self, conn: ConnectionHandler, tool_name: str, arguments: Dict[str, Any]
    ) -> ActionResponse:
        """Thực thi công cụ MCP phía máy chủ"""
        if not self._initialized or not self.mcp_manager:
            return ActionResponse(
                action=Action.ERROR,
                response="Bộ quản lý MCP chưa được khởi tạo",
            )

        try:
            # Loại bỏ tiền tố mcp_ nếu có
            actual_tool_name = tool_name
            if tool_name.startswith("mcp_"):
                actual_tool_name = tool_name[4:]

            result = await self.mcp_manager.execute_tool(actual_tool_name, arguments)

            return ActionResponse(action=Action.REQLLM, result=str(result))

        except ValueError as e:
            return ActionResponse(
                action=Action.NOTFOUND,
                response=str(e),
            )
        except Exception as e:
            return ActionResponse(
                action=Action.ERROR,
                response=str(e),
            )

    def get_tools(self) -> Dict[str, ToolDefinition]:
        """Lấy tất cả công cụ MCP phía máy chủ"""
        if not self._initialized or not self.mcp_manager:
            return {}

        tools = {}
        mcp_tools = self.mcp_manager.get_all_tools()

        for tool in mcp_tools:
            func_def = tool.get("function", {})
            tool_name = func_def.get("name", "")
            if tool_name == "":
                continue
            tools[tool_name] = ToolDefinition(
                name=tool_name, description=tool, tool_type=ToolType.SERVER_MCP
            )

        return tools

    def has_tool(self, tool_name: str) -> bool:
        """Kiểm tra xem có công cụ MCP phía máy chủ cụ thể hay không"""
        if not self._initialized or not self.mcp_manager:
            return False

        # Loại bỏ tiền tố mcp_ nếu có
        actual_tool_name = tool_name
        if tool_name.startswith("mcp_"):
            actual_tool_name = tool_name[4:]

        return self.mcp_manager.is_mcp_tool(actual_tool_name)

    async def cleanup(self):
        """Giải phóng kết nối MCP"""
        if self.mcp_manager:
            await self.mcp_manager.cleanup_all()
