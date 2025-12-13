"""Bộ thực thi công cụ điểm kết nối MCP"""
from __future__ import annotations
from typing import TYPE_CHECKING, Dict, Any
from ..base import ToolType, ToolDefinition, ToolExecutor
from app.ai.plugins_func.register import Action, ActionResponse
from .mcp_endpoint_handler import call_mcp_endpoint_tool
if TYPE_CHECKING:
    from app.ai.connection import ConnectionHandler  # chỉ dùng cho hint, không chạy lúc runtime


class MCPEndpointExecutor(ToolExecutor):
    """Bộ thực thi công cụ tại điểm kết nối MCP"""

    def __init__(self, conn: ConnectionHandler):
        self.conn = conn

    async def execute(
        self, conn: ConnectionHandler, tool_name: str, arguments: Dict[str, Any]
    ) -> ActionResponse:
        """Thực thi công cụ điểm kết nối MCP"""
        if not hasattr(conn, "mcp_endpoint_client") or not conn.mcp_endpoint_client:
            return ActionResponse(
                action=Action.ERROR,
                response="Client điểm kết nối MCP chưa được khởi tạo",
            )

        if not await conn.mcp_endpoint_client.is_ready():
            return ActionResponse(
                action=Action.ERROR,
                response="Client điểm kết nối MCP chưa sẵn sàng",
            )

        try:
            # Chuyển tham số thành chuỗi JSON
            import json

            args_str = json.dumps(arguments) if arguments else "{}"

            # Gọi công cụ trên điểm kết nối MCP
            result = await call_mcp_endpoint_tool(
                conn.mcp_endpoint_client, tool_name, args_str
            )

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
        """Lấy tất cả công cụ tại điểm kết nối MCP"""
        if (
            not hasattr(self.conn, "mcp_endpoint_client")
            or not self.conn.mcp_endpoint_client
        ):
            return {}

        tools = {}
        mcp_tools = self.conn.mcp_endpoint_client.get_available_tools()

        for tool in mcp_tools:
            func_def = tool.get("function", {})
            tool_name = func_def.get("name", "")

            if tool_name:
                tools[tool_name] = ToolDefinition(
                    name=tool_name, description=tool, tool_type=ToolType.MCP_ENDPOINT
                )

        return tools

    def has_tool(self, tool_name: str) -> bool:
        """Kiểm tra xem có công cụ điểm kết nối MCP cụ thể hay không"""
        if (
            not hasattr(self.conn, "mcp_endpoint_client")
            or not self.conn.mcp_endpoint_client
        ):
            return False

        return self.conn.mcp_endpoint_client.has_tool(tool_name)
