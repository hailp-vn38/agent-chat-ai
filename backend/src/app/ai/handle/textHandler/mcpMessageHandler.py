from __future__ import annotations
import asyncio
from typing import TYPE_CHECKING, Dict, Any
from app.ai.handle.textMessageHandler import TextMessageHandler
from app.ai.handle.textMessageType import TextMessageType
from app.ai.providers.tools.device_mcp import handle_mcp_message

if TYPE_CHECKING:
    from app.ai.connection import ConnectionHandler  # chỉ dùng cho hint, không chạy lúc runtime


class McpTextMessageHandler(TextMessageHandler):
    """Trình xử lý thông điệp MCP"""

    @property
    def message_type(self) -> TextMessageType:
        return TextMessageType.MCP

    async def handle(self, conn: ConnectionHandler, msg_json: Dict[str, Any]) -> None:
        if "payload" in msg_json:
            asyncio.create_task(
                handle_mcp_message(conn, conn.mcp_client, msg_json["payload"])
            )
