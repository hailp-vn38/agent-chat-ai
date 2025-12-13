from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any, Dict

from app.ai.handle.intentHandler import speak_txt
from app.ai.handle.textMessageHandler import TextMessageHandler
from app.ai.handle.textMessageType import TextMessageType
from app.core.logger import setup_logging

if TYPE_CHECKING:
    from app.ai.connection import ConnectionHandler  # chỉ dùng cho hint, không chạy lúc runtime


TAG = __name__


class SpeakTextMessageHandler(TextMessageHandler):
    """Trình xử lý thông điệp yêu cầu phát TTS trực tiếp"""

    def __init__(self) -> None:
        self.logger = setup_logging()

    @property
    def message_type(self) -> TextMessageType:
        return TextMessageType.SPEAK

    async def handle(self, conn: ConnectionHandler, msg_json: Dict[str, Any]) -> None:
        text = msg_json.get("text")
        if not isinstance(text, str) or not text.strip():
            await self._send_error(conn, "Thiếu trường 'text' hợp lệ trong thông điệp")
            return

        text = text.strip()
        pipeline_ready = await conn.wait_for_pipeline_ready(timeout=5)
        if not pipeline_ready or not getattr(conn, "tts", None):
            await self._send_error(
                conn, "Pipeline âm thanh/TTS chưa sẵn sàng, vui lòng thử lại sau"
            )
            return

        sentence_id = msg_json.get("sentence_id")
        if isinstance(sentence_id, str) and sentence_id.strip():
            conn.sentence_id = sentence_id.strip()
        else:
            conn.sentence_id = str(uuid.uuid4().hex)

        conn.client_abort = False
        speak_txt(conn, text)

        await conn.send_raw(
            {
                "type": TextMessageType.SPEAK.value,
                "status": "queued",
                "session_id": conn.session_id,
                "sentence_id": conn.sentence_id,
            }
        )

    async def _send_error(self, conn: ConnectionHandler, message: str) -> None:
        self.logger.bind(tag=TAG).warning(message)
        await conn.send_raw(
            {
                "type": TextMessageType.SPEAK.value,
                "status": "error",
                "message": message,
                "session_id": conn.session_id,
            }
        )
