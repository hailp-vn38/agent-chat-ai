"""
Tool phát nhạc từ URL qua FFmpeg streaming.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from app.ai.plugins_func.register import (
    register_function,
    ToolType,
    ActionResponse,
    Action,
)
from app.ai.handle.sendAudioHandle import send_stt_message, send_tts_message, sendAudio
from app.ai.utils.dialogue import Message
from app.ai.providers.audio.ffmpeg_streamer import FFmpegURLStreamer
from app.ai.providers.tts.dto.dto import SentenceType
from app.core.logger import setup_logging

if TYPE_CHECKING:
    from app.ai.connection import ConnectionHandler

TAG = __name__
logger = setup_logging()

# Frame duration cho Opus (ms) - phải khớp với FFmpeg config
FRAME_DURATION_MS = 60

stream_music_url_function_desc = {
    "type": "function",
    "function": {
        "name": "stream_music_url",
        "description": "Phát nhạc trực tuyến từ URL. Sử dụng sau khi tìm kiếm nhạc với search_music.",
        "parameters": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "URL stream của bài hát (từ kết quả search_music)",
                },
                "song_name": {
                    "type": "string",
                    "description": "Tên bài hát để hiển thị (optional)",
                    "default": "",
                },
            },
            "required": ["url"],
        },
    },
}


@register_function(
    "stream_music_url", stream_music_url_function_desc, ToolType.SYSTEM_CTL
)
def stream_music_url(conn: ConnectionHandler, url: str, song_name: str = ""):
    """
    Phát nhạc từ URL qua FFmpeg streaming.

    Args:
        conn: Connection handler
        url: Stream URL của bài hát
        song_name: Tên bài hát (optional)

    Returns:
        ActionResponse
    """
    try:
        logger.bind(tag=TAG).debug(
            f"[stream_music_url] url={url[:100]}..., song_name={song_name}"
        )

        # Validate URL
        if not url or not url.startswith(("http://", "https://")):
            logger.bind(tag=TAG).debug("[stream_music_url] Invalid URL format")
            return ActionResponse(
                action=Action.RESPONSE,
                result="URL không hợp lệ",
                response="URL nhạc không hợp lệ",
            )

        # Check FFmpeg availability
        ffmpeg_available = FFmpegURLStreamer.is_ffmpeg_available()
        logger.bind(tag=TAG).debug(
            f"[stream_music_url] FFmpeg available: {ffmpeg_available}"
        )
        if not ffmpeg_available:
            logger.bind(tag=TAG).error("[stream_music_url] FFmpeg không được cài đặt")
            return ActionResponse(
                action=Action.RESPONSE,
                result="FFmpeg không khả dụng",
                response="Hệ thống chưa sẵn sàng để phát nhạc trực tuyến",
            )

        # Check event loop
        if not conn.loop.is_running():
            logger.bind(tag=TAG).error("[stream_music_url] Event loop không chạy")
            return ActionResponse(
                action=Action.RESPONSE,
                result="Hệ thống bận",
                response="Vui lòng thử lại sau",
            )

        logger.bind(tag=TAG).debug("[stream_music_url] Creating stream task...")

        # Start streaming task
        task = conn.loop.create_task(_handle_stream(conn, url, song_name))

        def handle_done(f):
            try:
                f.result()
                logger.bind(tag=TAG).info(
                    "[stream_music_url] Stream hoàn tất thành công"
                )
            except asyncio.CancelledError:
                logger.bind(tag=TAG).debug("[stream_music_url] Stream bị hủy")
            except Exception as e:
                logger.bind(tag=TAG).error(
                    f"[stream_music_url] Stream error: {e}", exc_info=True
                )

        task.add_done_callback(handle_done)

        display_name = song_name if song_name else "bài hát"
        logger.bind(tag=TAG).debug(
            f"[stream_music_url] Task created, returning response"
        )
        return ActionResponse(
            action=Action.NONE,
            result="Đang phát nhạc",
            response=f"Đang phát {display_name} cho bạn",
        )

    except Exception as e:
        logger.bind(tag=TAG).error(f"[stream_music_url] Exception: {e}", exc_info=True)
        return ActionResponse(
            action=Action.ERROR,
            result=str(e),
            response="Có lỗi khi phát nhạc",
        )


async def _handle_stream(conn: ConnectionHandler, url: str, song_name: str):
    """
    Xử lý streaming nhạc từ URL.

    Gửi trực tiếp qua WebSocket, bypass TTS queue để tránh conflict với LLM response.

    Args:
        conn: Connection handler
        url: Stream URL
        song_name: Tên bài hát
    """
    logger.bind(tag=TAG).debug(
        f"[_handle_stream] Starting stream for: {song_name or url[:50]}"
    )

    streamer = FFmpegURLStreamer(url, frame_duration_ms=FRAME_DURATION_MS)

    # Store streamer reference for stop_music
    conn.current_streamer = streamer
    logger.bind(tag=TAG).debug("[_handle_stream] Streamer created and stored in conn")

    try:
        # Send notification
        display_name = song_name if song_name else "nhạc"
        notification = f"Đang phát {display_name}"
        await send_stt_message(conn, notification)
        conn.dialogue.put(Message(role="assistant", content=notification))
        logger.bind(tag=TAG).debug("[_handle_stream] Sent STT notification")

        # Send TTS start signal - notify client music is starting
        await send_tts_message(conn, "start", None)
        logger.bind(tag=TAG).debug("[_handle_stream] Sent TTS start signal")

        # Stream audio frames - gửi trực tiếp, không qua TTS queue
        frame_count = 0
        total_bytes = 0
        logger.bind(tag=TAG).debug("[_handle_stream] Starting to stream frames...")

        async for opus_frame in streamer.stream_opus_frames():
            # Check abort
            if conn.client_abort:
                logger.bind(tag=TAG).debug(
                    f"[_handle_stream] Aborted at frame {frame_count}"
                )
                break

            # Gửi trực tiếp qua WebSocket với flow control
            # sendAudio đã có sẵn pacing logic
            await sendAudio(conn, opus_frame, frame_duration=FRAME_DURATION_MS)

            frame_count += 1
            total_bytes += len(opus_frame)

            # Log progress periodically
            if frame_count % 500 == 0:
                logger.bind(tag=TAG).debug(
                    f"[_handle_stream] Progress: {frame_count} frames, {total_bytes} bytes, "
                    f"avg_size={total_bytes // frame_count} bytes/frame"
                )

        logger.bind(tag=TAG).info(
            f"[_handle_stream] Stream completed: {frame_count} frames, {total_bytes} bytes"
        )

    except asyncio.CancelledError:
        logger.bind(tag=TAG).debug("[_handle_stream] Task cancelled")
        raise
    except Exception as e:
        logger.bind(tag=TAG).error(f"[_handle_stream] Exception: {e}", exc_info=True)
    finally:
        # Cleanup
        logger.bind(tag=TAG).debug("[_handle_stream] Cleaning up...")
        await streamer.stop_async()
        conn.current_streamer = None

        # Send stop signal
        if not conn.client_abort:
            await send_tts_message(conn, "stop", None)
            logger.bind(tag=TAG).debug("[_handle_stream] Sent TTS stop signal")

        conn.clearSpeakStatus()
        logger.bind(tag=TAG).debug("[_handle_stream] Cleanup done")
