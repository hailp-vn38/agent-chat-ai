from __future__ import annotations
from typing import Dict, Any,TYPE_CHECKING
from app.ai.handle.abortHandle import handleAbortMessage
from app.ai.handle.textMessageHandler import TextMessageHandler
from app.ai.handle.textMessageType import TextMessageType
if TYPE_CHECKING:
    from app.ai.connection import ConnectionHandler  # chỉ dùng cho hint, không chạy lúc runtime


class AbortTextMessageHandler(TextMessageHandler):
    """Trình xử lý thông điệp Abort"""

    @property
    def message_type(self) -> TextMessageType:
        return TextMessageType.ABORT

    async def handle(self, conn: ConnectionHandler, msg_json: Dict[str, Any]) -> None:
        await handleAbortMessage(conn)
