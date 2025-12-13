from __future__ import annotations

import json
import uuid
from typing import TYPE_CHECKING, Any, Dict, Optional

from app.ai.handle.intentHandler import speak_txt
from app.ai.handle.textMessageHandler import TextMessageHandler
from app.ai.handle.textMessageType import TextMessageType
from app.core.logger import setup_logging

if TYPE_CHECKING:
    from app.ai.connection import (
        ConnectionHandler,
    )  # chỉ dùng cho hint, không chạy lúc runtime


TAG = __name__


class NotificationProcessor:
    """Static processor for notification delivery modes"""

    @staticmethod
    async def process_with_llm(
        conn: ConnectionHandler,
        title: str,
        content: str,
    ) -> None:
        """
        Deliver notification through LLM pipeline.

        Flow:
        1. Build system prompt with context
        2. Wait for pipeline ready (TTS, LLM, etc.)
        3. Submit to LLM for processing
        """
        prompt = NotificationProcessor._build_system_prompt(
            title=title,
            content=content,
        )

        await conn.wait_for_pipeline_ready(timeout=5)
        conn.submit_blocking_task(conn.chat, prompt)

    @staticmethod
    async def process_with_tts(
        conn: ConnectionHandler,
        content: str,
        sentence_id: Optional[str] = None,
    ) -> None:
        """
        Deliver notification directly via TTS (no LLM).

        Flow:
        1. Validate content
        2. Wait for TTS pipeline ready
        3. Queue text to TTS
        """
        if not content or not content.strip():
            raise ValueError("Content cannot be empty")

        pipeline_ready = await conn.wait_for_pipeline_ready(timeout=5)
        if not pipeline_ready or not getattr(conn, "tts", None):
            raise RuntimeError("TTS pipeline not ready")

        # Generate sentence_id if not provided
        if not sentence_id:
            sentence_id = str(uuid.uuid4().hex)

        conn.sentence_id = sentence_id
        conn.client_abort = False

        # Use imported speak_txt function
        speak_txt(conn, content)

    @staticmethod
    def _build_system_prompt(
        title: str,
        content: str,
    ) -> str:
        """Build system prompt for LLM with context"""
        lines = [
            "[SYSTEM NOTIFICATION]",
            "This is a system message, not from the user. Please deliver the message to the user.",
        ]

        if title:
            lines.append(f"Title: {title}")

        lines.append(f"Message: {content}")

        return "\n".join(lines)


class NotificationMessageHandler(TextMessageHandler):
    """Trình xử lý thông điệp notification với chế độ delivery linh hoạt"""

    def __init__(self):
        self.logger = setup_logging()

    @property
    def message_type(self) -> TextMessageType:
        return TextMessageType.NOTIFICATION

    async def handle(self, conn: ConnectionHandler, msg_json: Dict[str, Any]) -> None:
        """
        Route notification to appropriate processor based on delivery mode.

        if useLLM=true: Process through LLM pipeline
        if useLLM=false: Deliver directly via TTS
        """
        # 1. Extract and validate fields
        use_llm = msg_json.get("useLLM", False)
        title = msg_json.get("title", "")
        content = msg_json.get("content", "")

        if not content or not isinstance(content, str):
            await self._send_error(conn, "Missing or invalid 'content' field")
            return

        # 2. Route to appropriate processor
        try:
            if use_llm:
                await NotificationProcessor.process_with_llm(
                    conn,
                    title=title,
                    content=content,
                )
            else:
                await NotificationProcessor.process_with_tts(
                    conn,
                    content=content,
                    sentence_id=msg_json.get("sentence_id"),
                )
        except Exception as e:
            await self._send_error(conn, f"Processing failed: {str(e)}")

    async def _send_error(self, conn: ConnectionHandler, message: str) -> None:
        conn.logger.bind(tag=TAG).warning(f"Lỗi xử lý notification: {message}")
        await conn.send_raw(
            json.dumps(
                {
                    "type": self.message_type.value,
                    "status": "error",
                    "message": message,
                    "session_id": conn.session_id,
                }
            )
        )
