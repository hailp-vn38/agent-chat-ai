"""
Tool tìm kiếm video YouTube sử dụng pytubefix.
Không cần API key.
"""

from __future__ import annotations

import traceback
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

search_youtube_function_desc = {
    "type": "function",
    "function": {
        "name": "search_youtube",
        "description": "Tìm kiếm video trên YouTube. Trả về danh sách video với tên, tác giả, thời lượng và URL.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Từ khóa tìm kiếm (tên bài hát, nghệ sĩ, hoặc nội dung)",
                },
                "limit": {
                    "type": "integer",
                    "description": "Số lượng kết quả tối đa (mặc định: 5, tối đa: 10)",
                    "default": 5,
                },
            },
            "required": ["query"],
        },
    },
}


@register_function("search_youtube", search_youtube_function_desc, ToolType.SYSTEM_CTL)
def search_youtube(conn: ConnectionHandler, query: str, limit: int = 5):
    """
    Tìm kiếm video YouTube.

    Args:
        conn: Connection handler
        query: Từ khóa tìm kiếm
        limit: Số kết quả tối đa (1-10)

    Returns:
        ActionResponse với danh sách video hoặc error message
    """
    try:
        # Validate limit
        limit = max(1, min(10, limit))
        logger.bind(tag=TAG).debug(f"[search_youtube] query='{query}', limit={limit}")

        # Import pytubefix here to avoid startup delay
        from pytubefix import Search

        search = Search(query)
        results = []

        for video in search.videos[:limit]:
            results.append(
                {
                    "video_id": video.video_id,
                    "title": video.title,
                    "author": video.author,
                    "duration": video.length,  # seconds
                    "views": video.views,
                    "url": video.watch_url,
                }
            )

        logger.bind(tag=TAG).debug(f"[search_youtube] Found {len(results)} videos")

        if not results:
            return ActionResponse(
                action=Action.RESPONSE,
                result="Không tìm thấy video nào",
                response=f"Không tìm thấy video nào với từ khóa '{query}'",
            )

        # Format result for LLM
        formatted = _format_results_for_llm(results)
        logger.bind(tag=TAG).debug(f"[search_youtube] Formatted:\n{formatted}")

        return ActionResponse(
            action=Action.REQLLM,
            result=formatted,
            response=None,
        )

    except Exception as e:
        error_msg = f"{type(e).__name__}: {e}" if str(e) else type(e).__name__
        logger.bind(tag=TAG).error(
            f"[search_youtube] Exception: {error_msg}\n"
            f"Traceback:\n{traceback.format_exc()}"
        )
        return ActionResponse(
            action=Action.ERROR,
            result=error_msg,
            response="Có lỗi xảy ra khi tìm kiếm YouTube",
        )


def _format_results_for_llm(results: list[dict]) -> str:
    """Format danh sách video để LLM đọc và chọn."""
    lines = ["Kết quả tìm kiếm YouTube:"]

    for i, video in enumerate(results, 1):
        duration = video["duration"] or 0
        duration_min = duration // 60
        duration_sec = duration % 60
        views = f"{video['views']:,}" if video["views"] else "N/A"

        lines.append(
            f"{i}. {video['title']} - {video['author']} ({duration_min}:{duration_sec:02d})"
        )
        lines.append(f"   Views: {views}")
        lines.append(f"   Video ID: {video['video_id']}")

    lines.append(
        "\n[Hướng dẫn cho AI]:"
        "\n- Khi trả lời người dùng, CHỈ nhắc tên bài hát/video (title), KHÔNG đề cập URL hay video_id."
        "\n- Hỏi người dùng muốn nghe bài nào (theo số thứ tự hoặc tên)."
        "\n- Khi người dùng chọn, dùng play_youtube với video_id tương ứng để phát."
    )

    return "\n".join(lines)
