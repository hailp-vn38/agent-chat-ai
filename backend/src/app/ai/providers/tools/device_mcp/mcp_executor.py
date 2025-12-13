"""Bộ thực thi công cụ MCP phía thiết bị"""
from __future__ import annotations
from typing import TYPE_CHECKING, Dict, Any
from ..base import ToolType, ToolDefinition, ToolExecutor
from app.ai.plugins_func.register import Action, ActionResponse
from .mcp_handler import call_mcp_tool
if TYPE_CHECKING:
    from app.ai.connection import ConnectionHandler  # chỉ dùng cho hint, không chạy lúc runtime


class DeviceMCPExecutor(ToolExecutor):
    """Bộ thực thi công cụ MCP dành cho thiết bị"""

    def __init__(self, conn: ConnectionHandler):
        self.conn = conn

    async def execute(
        self, conn: ConnectionHandler, tool_name: str, arguments: Dict[str, Any]
    ) -> ActionResponse:
        """Thực thi công cụ MCP phía thiết bị"""
        if not hasattr(conn, "mcp_client") or not conn.mcp_client:
            return ActionResponse(
                action=Action.ERROR,
                response="Client MCP phía thiết bị chưa được khởi tạo",
            )

        if not await conn.mcp_client.is_ready():
            return ActionResponse(
                action=Action.ERROR,
                response="Client MCP phía thiết bị chưa sẵn sàng",
            )

        try:
            # Chuyển tham số thành chuỗi JSON
            import json

            args_str = json.dumps(arguments) if arguments else "{}"

            # Gọi công cụ MCP phía thiết bị
            result = await call_mcp_tool(conn, conn.mcp_client, tool_name, args_str)

            resultJson = None
            if isinstance(result, str):
                try:
                    resultJson = json.loads(result)
                except Exception:
                    pass

            # Mô hình thị giác không cần xử lý LLM lần hai
            if (
                resultJson is not None
                and isinstance(resultJson, dict)
                and "action" in resultJson
            ):
                return ActionResponse(
                    action=Action[resultJson["action"]],
                    response=resultJson.get("response", ""),
                )

            return ActionResponse(action=Action.REQLLM, result=str(result))

        except ValueError as e:
            return ActionResponse(action=Action.NOTFOUND, response=str(e))
        except Exception as e:
            return ActionResponse(action=Action.ERROR, response=str(e))

    def get_tools(self) -> Dict[str, ToolDefinition]:
        """Lấy toàn bộ công cụ MCP phía thiết bị"""
        if not hasattr(self.conn, "mcp_client") or not self.conn.mcp_client:
            return {}

        tools = {}
        mcp_tools = self.conn.mcp_client.get_available_tools()

        for tool in mcp_tools:
            func_def = tool.get("function", {})
            tool_name = func_def.get("name", "")

            if tool_name:
                tools[tool_name] = ToolDefinition(
                    name=tool_name, description=tool, tool_type=ToolType.DEVICE_MCP
                )

        return tools

    def has_tool(self, tool_name: str) -> bool:
        """Kiểm tra xem có công cụ MCP phía thiết bị cụ thể hay không"""
        if not hasattr(self.conn, "mcp_client") or not self.conn.mcp_client:
            return False

        return self.conn.mcp_client.has_tool(tool_name)
