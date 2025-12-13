from __future__ import annotations
import asyncio
from typing import Dict, Any,TYPE_CHECKING
from app.ai.handle.textMessageHandler import TextMessageHandler
from app.ai.handle.textMessageType import TextMessageType
from app.ai.providers.tools.device_iot import handleIotStatus, handleIotDescriptors

if TYPE_CHECKING:
    from app.ai.connection import ConnectionHandler  # chỉ dùng cho hint, không chạy lúc runtime

class IotTextMessageHandler(TextMessageHandler):
    """Trình xử lý thông điệp IOT"""

    @property
    def message_type(self) -> TextMessageType:
        return TextMessageType.IOT

    async def handle(self, conn: ConnectionHandler, msg_json: Dict[str, Any]) -> None:
        if "descriptors" in msg_json:
            asyncio.create_task(handleIotDescriptors(conn, msg_json["descriptors"]))
        if "states" in msg_json:
            asyncio.create_task(handleIotStatus(conn, msg_json["states"]))
