"""
Tool tìm kiếm nhạc từ NhacCuaTui API.

API endpoint: https://graph.nhaccuatui.com/api/v1/search/song
"""

from __future__ import annotations

import time
import traceback
from typing import TYPE_CHECKING
import requests

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

# API config
NHACCUATUI_SEARCH_URL = "https://graph.nhaccuatui.com/api/v1/search/song"
REQUEST_TIMEOUT = 15  # seconds

search_music_function_desc = {
    "type": "function",
    "function": {
        "name": "search_music",
        "description": "Tìm kiếm bài hát từ NhacCuaTui. Trả về danh sách bài hát với tên, nghệ sĩ và URL stream.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Từ khóa tìm kiếm (tên bài hát hoặc tên nghệ sĩ)",
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


@register_function("search_music", search_music_function_desc, ToolType.SYSTEM_CTL)
def search_music(conn: ConnectionHandler, query: str, limit: int = 5):
    """
    Tìm kiếm nhạc từ NhacCuaTui (sync version).

    Args:
        conn: Connection handler
        query: Từ khóa tìm kiếm
        limit: Số kết quả tối đa (1-10)

    Returns:
        ActionResponse với danh sách bài hát hoặc error message
    """
    try:
        # Validate limit
        limit = max(1, min(10, limit))
        logger.bind(tag=TAG).debug(f"[search_music] query='{query}', limit={limit}")

        # Gọi sync API (không dùng async vì event loop có thể bận)
        result = _search_nhaccuatui_sync(query, limit)

        logger.bind(tag=TAG).debug(
            f"[search_music] result type={type(result).__name__}"
        )

        if result is None:
            logger.bind(tag=TAG).debug("[search_music] No songs found")
            return ActionResponse(
                action=Action.RESPONSE,
                result="Không tìm thấy bài hát nào",
                response=f"Không tìm thấy bài hát nào với từ khóa '{query}'",
            )

        if isinstance(result, str):
            # Error message
            logger.bind(tag=TAG).debug(f"[search_music] Error: {result}")
            return ActionResponse(
                action=Action.RESPONSE,
                result=result,
                response=result,
            )

        # Format result for LLM
        logger.bind(tag=TAG).debug(f"[search_music] Found {len(result)} songs")
        songs_text = _format_songs_for_llm(result)
        logger.bind(tag=TAG).debug(f"[search_music] Formatted result:\n{songs_text}")

        return ActionResponse(
            action=Action.REQLLM,
            result=songs_text,
            response=None,
        )

    except requests.Timeout:
        logger.bind(tag=TAG).error(
            f"[search_music] Request timeout\nTraceback:\n{traceback.format_exc()}"
        )
        return ActionResponse(
            action=Action.RESPONSE,
            result="Hết thời gian chờ",
            response="Không thể kết nối đến dịch vụ nhạc, vui lòng thử lại sau",
        )
    except Exception as e:
        error_msg = f"{type(e).__name__}: {e}" if str(e) else type(e).__name__
        logger.bind(tag=TAG).error(
            f"[search_music] Exception: {error_msg}\n"
            f"Traceback:\n{traceback.format_exc()}"
        )
        return ActionResponse(
            action=Action.ERROR,
            result=error_msg,
            response="Có lỗi xảy ra khi tìm kiếm nhạc",
        )


def _search_nhaccuatui_sync(query: str, limit: int) -> list[dict] | str | None:
    """
    Gọi NhacCuaTui API để tìm kiếm bài hát (sync version với requests).

    Returns:
        - List of songs nếu thành công
        - String error message nếu có lỗi
        - None nếu không tìm thấy
    """
    logger.bind(tag=TAG).debug(
        f"[_search_nhaccuatui_sync] STARTED - query='{query}', limit={limit}"
    )

    try:
        params = {
            "keyword": query,
            "pageindex": 1,
            "pagesize": limit,
            "correct": "false",
            "timestamp": int(time.time() * 1000),
        }

        logger.bind(tag=TAG).debug(
            f"[_search_nhaccuatui_sync] URL: {NHACCUATUI_SEARCH_URL}"
        )
        logger.bind(tag=TAG).debug(f"[_search_nhaccuatui_sync] Params: {params}")
        logger.bind(tag=TAG).debug(
            f"[_search_nhaccuatui_sync] Timeout: {REQUEST_TIMEOUT}s"
        )

        logger.bind(tag=TAG).debug("[_search_nhaccuatui_sync] Sending GET request...")
        response = requests.get(
            NHACCUATUI_SEARCH_URL,
            params=params,
            timeout=REQUEST_TIMEOUT,
        )

        logger.bind(tag=TAG).debug(
            f"[_search_nhaccuatui_sync] Response status: {response.status_code}"
        )
        response.raise_for_status()

        logger.bind(tag=TAG).debug("[_search_nhaccuatui_sync] Parsing JSON...")
        data = response.json()

        logger.bind(tag=TAG).debug(
            f"[_search_nhaccuatui_sync] API response: code={data.get('code')}, "
            f"success={data.get('success')}, msg={data.get('msg')}"
        )

        if data.get("code") != 0 or not data.get("success"):
            logger.bind(tag=TAG).warning(
                f"[_search_nhaccuatui_sync] API error: {data.get('msg')}"
            )
            return "Dịch vụ nhạc tạm thời không khả dụng"

        songs_data = data.get("data", {}).get("songs", [])
        logger.bind(tag=TAG).debug(
            f"[_search_nhaccuatui_sync] Raw songs count: {len(songs_data)}"
        )

        if not songs_data:
            return None

        # Extract relevant info
        songs = []
        for i, song in enumerate(songs_data):
            stream_url = _get_stream_url(song)
            logger.bind(tag=TAG).debug(
                f"[_search_nhaccuatui_sync] Song {i}: name={song.get('name')}, "
                f"stream_url={'found' if stream_url else 'NOT FOUND'}"
            )
            if not stream_url:
                continue

            songs.append(
                {
                    "name": song.get("name", "Unknown"),
                    "artist_name": song.get("artistName", "Unknown"),
                    "stream_url": stream_url,
                    "duration": song.get("duration", 0),
                }
            )

        logger.bind(tag=TAG).debug(
            f"[_search_nhaccuatui_sync] Valid songs: {len(songs)}"
        )
        return songs if songs else None

    except requests.Timeout:
        logger.bind(tag=TAG).error(
            f"[_search_nhaccuatui_sync] Timeout after {REQUEST_TIMEOUT}s\n"
            f"URL: {NHACCUATUI_SEARCH_URL}\n"
            f"Traceback:\n{traceback.format_exc()}"
        )
        return "Hết thời gian chờ kết nối"
    except requests.HTTPError as e:
        logger.bind(tag=TAG).error(
            f"[_search_nhaccuatui_sync] HTTP error: {e.response.status_code}\n"
            f"Response: {e.response.text[:500] if e.response.text else 'N/A'}\n"
            f"Traceback:\n{traceback.format_exc()}"
        )
        return "Lỗi kết nối đến dịch vụ nhạc"
    except requests.RequestException as e:
        logger.bind(tag=TAG).error(
            f"[_search_nhaccuatui_sync] Request error: {type(e).__name__}: {e}\n"
            f"URL: {NHACCUATUI_SEARCH_URL}\n"
            f"Traceback:\n{traceback.format_exc()}"
        )
        return f"Lỗi kết nối: {type(e).__name__}"
    except Exception as e:
        error_msg = f"{type(e).__name__}: {e}" if str(e) else type(e).__name__
        logger.bind(tag=TAG).error(
            f"[_search_nhaccuatui_sync] Exception: {error_msg}\n"
            f"Traceback:\n{traceback.format_exc()}"
        )
        return f"Lỗi: {error_msg}"


def _get_stream_url(song: dict) -> str | None:
    """
    Lấy stream URL 128kbps từ song data.

    Ưu tiên:
    1. streamURL[type="128"] với onlyVIP=false
    2. streamURL đầu tiên với onlyVIP=false
    """
    stream_urls = song.get("streamURL", [])
    if not stream_urls:
        return None

    # Tìm 128kbps non-VIP
    for stream in stream_urls:
        if (
            stream.get("type") == "128"
            and not stream.get("onlyVIP", True)
            and stream.get("stream")
        ):
            return stream["stream"]

    # Fallback: bất kỳ non-VIP stream nào
    for stream in stream_urls:
        if not stream.get("onlyVIP", True) and stream.get("stream"):
            return stream["stream"]

    return None


def _format_songs_for_llm(songs: list[dict]) -> str:
    """Format danh sách bài hát để LLM có thể đọc và chọn."""
    lines = ["Kết quả tìm kiếm nhạc:"]

    for i, song in enumerate(songs, 1):
        duration_min = song["duration"] // 60
        duration_sec = song["duration"] % 60
        lines.append(
            f"{i}. {song['name']} - {song['artist_name']} ({duration_min}:{duration_sec:02d})"
        )
        lines.append(f"   URL: {song['stream_url']}")

    lines.append(
        "\nHãy hỏi người dùng muốn nghe bài nào hoặc tự động phát bài đầu tiên nếu chỉ có 1 kết quả."
    )

    return "\n".join(lines)
