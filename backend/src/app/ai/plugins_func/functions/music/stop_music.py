"""
Tool dừng phát nhạc đang chơi.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.ai.plugins_func.register import (
    register_function,
    ToolType,
    ActionResponse,
    Action,
)
from app.core.logger import setup_logging

if TYPE_CHECKING:
    from app.ai.connection import ConnectionHandler

TAG = __name__
logger = setup_logging()

stop_music_function_desc = {
    "type": "function",
    "function": {
        "name": "stop_music",
        "description": "Dừng phát nhạc đang chơi. Sử dụng khi người dùng muốn tắt nhạc, dừng nhạc, hoặc ngừng phát.",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
}


@register_function("stop_music", stop_music_function_desc, ToolType.SYSTEM_CTL)
def stop_music(conn: ConnectionHandler):
    """
    Dừng phát nhạc đang chơi.

    Args:
        conn: Connection handler

    Returns:
        ActionResponse với confirmation message
    """
    try:
        logger.bind(tag=TAG).debug("[stop_music] Called")

        was_playing = False
        has_streamer = (
            hasattr(conn, "current_streamer") and conn.current_streamer is not None
        )
        has_tts = conn.tts is not None

        logger.bind(tag=TAG).debug(
            f"[stop_music] State: has_streamer={has_streamer}, "
            f"has_tts={has_tts}, client_abort={conn.client_abort}"
        )

        # Set abort flag để stop các loop
        conn.client_abort = True
        logger.bind(tag=TAG).debug("[stop_music] Set client_abort=True")

        # Stop FFmpeg streamer nếu có
        if has_streamer:
            logger.bind(tag=TAG).debug("[stop_music] Stopping FFmpeg streamer...")
            conn.current_streamer.stop()
            conn.current_streamer = None
            was_playing = True
            logger.bind(tag=TAG).debug("[stop_music] FFmpeg streamer stopped")

        # Clear audio queues
        if has_tts:
            queue_size_before = conn.tts.tts_audio_queue.qsize()
            conn.clear_queues()
            logger.bind(tag=TAG).debug(
                f"[stop_music] Cleared queues (was {queue_size_before} items)"
            )
            was_playing = True

        # Clear speak status
        conn.clearSpeakStatus()

        if was_playing:
            logger.bind(tag=TAG).info("[stop_music] Đã dừng phát nhạc thành công")
            return ActionResponse(
                action=Action.RESPONSE,
                result="Đã dừng nhạc",
                response="Đã dừng phát nhạc",
            )
        else:
            logger.bind(tag=TAG).debug("[stop_music] Không có nhạc đang phát")
            return ActionResponse(
                action=Action.RESPONSE,
                result="Không có nhạc đang phát",
                response="Hiện không có nhạc đang phát",
            )

    except Exception as e:
        logger.bind(tag=TAG).error(f"[stop_music] Exception: {e}", exc_info=True)
        return ActionResponse(
            action=Action.ERROR,
            result=str(e),
            response="Có lỗi khi dừng nhạc",
        )
