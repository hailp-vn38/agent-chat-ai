from __future__ import annotations
import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.ai.connection import ConnectionHandler  # chỉ dùng cho hint, không chạy lúc runtime


TAG = __name__


async def handleAbortMessage(conn: ConnectionHandler):
    conn.logger.bind(tag=TAG).info("Abort message received")
    # Đặt trạng thái thành hủy để tự động ngắt nhiệm vụ LLM và TTS
    conn.client_abort = True
    conn.clear_queues()
    # Ngắt trạng thái đang nói của client
    await conn.send_text(
        json.dumps({"type": "tts", "state": "stop", "session_id": conn.session_id})
    )
    conn.clearSpeakStatus()
    conn.logger.bind(tag=TAG).info("Abort message received-end")
