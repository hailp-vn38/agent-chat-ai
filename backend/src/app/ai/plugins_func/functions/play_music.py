from __future__ import annotations

import os
import re
import time
import random
import difflib
import traceback
from pathlib import Path
from typing import TYPE_CHECKING
from app.ai.handle.sendAudioHandle import send_stt_message
from app.ai.plugins_func.register import (
    register_function,
    ToolType,
    ActionResponse,
    Action,
)
from app.ai.utils.dialogue import Message
from app.ai.providers.tts.dto.dto import TTSMessageDTO, SentenceType, ContentType


if TYPE_CHECKING:
    from app.ai.connection import (
        ConnectionHandler,
    )  # chỉ dùng cho hint, không chạy lúc runtime


TAG = __name__

MUSIC_CACHE = {}

play_music_function_desc = {
    "type": "function",
    "function": {
        "name": "play_music",
        "description": "Phương thức để hát, nghe và phát nhạc.",
        "parameters": {
            "type": "object",
            "properties": {
                "song_name": {
                    "type": "string",
                    "description": "Tên bài hát; nếu người dùng không chỉ rõ thì dùng 'random'. Khi chỉ rõ sẽ trả về tên nhạc. Ví dụ: ```Người dùng: phát bài Hai Con Hổ\nTham số: Liang Zhi Lao Hu``` ```Người dùng: phát nhạc \nTham số: random ```",
                }
            },
            "required": ["song_name"],
        },
    },
}


@register_function("play_music", play_music_function_desc, ToolType.SYSTEM_CTL)
def play_music(conn: ConnectionHandler, song_name: str):
    try:
        music_intent = (
            f"phát nhạc {song_name}"
            if song_name != "random"
            else "phát nhạc ngẫu nhiên"
        )

        # Kiểm tra trạng thái vòng lặp sự kiện
        if not conn.loop.is_running():
            conn.logger.bind(tag=TAG).error(
                "Vòng lặp sự kiện chưa chạy, không thể gửi nhiệm vụ"
            )
            return ActionResponse(
                action=Action.RESPONSE,
                result="Hệ thống bận",
                response="Vui lòng thử lại sau",
            )

        # Gửi nhiệm vụ bất đồng bộ
        task = conn.loop.create_task(
            handle_music_command(conn, music_intent)
        )  # Đóng gói logic async

        # Xử lý callback không chặn
        def handle_done(f):
            try:
                f.result()  # Có thể xử lý logic thành công tại đây
                conn.logger.bind(tag=TAG).info("Phát nhạc xong")
            except Exception as e:
                conn.logger.bind(tag=TAG).error(f"Phát nhạc thất bại: {e}")

        task.add_done_callback(handle_done)

        return ActionResponse(
            action=Action.NONE, result="Đã nhận lệnh", response="Đang phát nhạc cho bạn"
        )
    except Exception as e:
        conn.logger.bind(tag=TAG).error(f"Lỗi khi xử lý ý định phát nhạc: {e}")
        return ActionResponse(
            action=Action.RESPONSE, result=str(e), response="Có lỗi khi phát nhạc"
        )


def _extract_song_name(text):
    """Trích xuất tên bài hát từ câu người dùng"""
    for keyword in ["phát nhạc"]:
        if keyword in text:
            parts = text.split(keyword)
            if len(parts) > 1:
                return parts[1].strip()
    return None


def _find_best_match(potential_song, music_files):
    """Tìm bài hát khớp nhất"""
    best_match = None
    highest_ratio = 0

    for music_file in music_files:
        song_name = os.path.splitext(music_file)[0]
        ratio = difflib.SequenceMatcher(None, potential_song, song_name).ratio()
        if ratio > highest_ratio and ratio > 0.4:
            highest_ratio = ratio
            best_match = music_file
    return best_match


def get_music_files(music_dir, music_ext):
    music_dir = Path(music_dir)
    music_files = []
    music_file_names = []

    if not music_dir.exists():
        return music_files, music_file_names

    for file in music_dir.rglob("*"):
        # Kiểm tra xem có phải tệp hay không
        if file.is_file():
            # Lấy phần mở rộng tập tin
            ext = file.suffix.lower()
            # Kiểm tra phần mở rộng có nằm trong danh sách không
            if ext in music_ext:
                # Thêm đường dẫn tương đối
                music_files.append(str(file.relative_to(music_dir)))
                music_file_names.append(
                    os.path.splitext(str(file.relative_to(music_dir)))[0]
                )
    return music_files, music_file_names


def initialize_music_handler(conn):
    global MUSIC_CACHE
    if MUSIC_CACHE == {}:
        if "play_music" in conn.config["plugins"]:
            MUSIC_CACHE["music_config"] = conn.config["plugins"]["play_music"]
            music_dir_config = MUSIC_CACHE["music_config"].get("music_dir", "")

            # Nếu config cung cấp đường dẫn, dùng đó; không thì dùng default từ paths
            if music_dir_config:
                MUSIC_CACHE["music_dir"] = os.path.abspath(music_dir_config)
            else:
                # Lazy import để tránh circular dependency
                from app.ai.utils.paths import get_music_dir

                MUSIC_CACHE["music_dir"] = str(get_music_dir())

            MUSIC_CACHE["music_ext"] = MUSIC_CACHE["music_config"].get(
                "music_ext", (".mp3", ".wav", ".p3")
            )
            MUSIC_CACHE["refresh_time"] = MUSIC_CACHE["music_config"].get(
                "refresh_time", 60
            )
        else:
            # Nếu không có config, dùng default từ paths
            from app.ai.utils.paths import get_music_dir

            MUSIC_CACHE["music_dir"] = str(get_music_dir())
            MUSIC_CACHE["music_ext"] = (".mp3", ".wav", ".p3")
            MUSIC_CACHE["refresh_time"] = 60

        # Lấy danh sách tệp nhạc
        MUSIC_CACHE["music_files"], MUSIC_CACHE["music_file_names"] = get_music_files(
            MUSIC_CACHE["music_dir"], MUSIC_CACHE["music_ext"]
        )
        MUSIC_CACHE["scan_time"] = time.time()

    return MUSIC_CACHE


async def handle_music_command(conn: ConnectionHandler, text: str):
    initialize_music_handler(conn)
    global MUSIC_CACHE

    """Xử lý lệnh phát nhạc"""
    clean_text = re.sub(r"[^\w\s]", "", text).strip()
    conn.logger.bind(tag=TAG).debug(
        f"Kiểm tra xem đây có phải lệnh phát nhạc: {clean_text}"
    )

    # Thử khớp với tên bài cụ thể
    if os.path.exists(MUSIC_CACHE["music_dir"]):
        if time.time() - MUSIC_CACHE["scan_time"] > MUSIC_CACHE["refresh_time"]:
            # Làm mới danh sách tệp nhạc
            MUSIC_CACHE["music_files"], MUSIC_CACHE["music_file_names"] = (
                get_music_files(MUSIC_CACHE["music_dir"], MUSIC_CACHE["music_ext"])
            )
            MUSIC_CACHE["scan_time"] = time.time()

        potential_song = _extract_song_name(clean_text)
        if potential_song:
            best_match = _find_best_match(potential_song, MUSIC_CACHE["music_files"])
            if best_match:
                conn.logger.bind(tag=TAG).info(
                    f"Tìm thấy bài hát khớp nhất: {best_match}"
                )
                await play_local_music(conn, specific_file=best_match)
                return True
    # Kiểm tra xem có phải lệnh phát nhạc chung không
    await play_local_music(conn)
    return True


def _get_random_play_prompt(song_name):
    """Tạo lời dẫn ngẫu nhiên khi phát"""
    # Loại bỏ phần mở rộng tệp
    clean_name = os.path.splitext(song_name)[0]
    prompts = [
        f"Đang phát cho bạn, “{clean_name}”",
        f"Mời bạn thưởng thức bài hát “{clean_name}”",
        f"Sắp phát cho bạn “{clean_name}”",
        f"Ngay bây giờ xin gửi tới bạn “{clean_name}”",
        f"Hãy cùng lắng nghe “{clean_name}”",
        f"Tiếp theo mời bạn thưởng thức “{clean_name}”",
        f"Khoảnh khắc này xin dành tặng bạn “{clean_name}”",
    ]
    # Sử dụng random.choice trực tiếp, không đặt seed
    return random.choice(prompts)


async def play_local_music(conn: ConnectionHandler, specific_file=None):
    global MUSIC_CACHE
    """Phát tệp nhạc nội bộ"""
    try:
        if not os.path.exists(MUSIC_CACHE["music_dir"]):
            conn.logger.bind(tag=TAG).error(
                f"Thư mục nhạc không tồn tại: {MUSIC_CACHE['music_dir']}"
            )
            return

        # Đảm bảo đường dẫn chính xác
        if specific_file:
            selected_music = specific_file
            music_path = os.path.join(MUSIC_CACHE["music_dir"], specific_file)
        else:
            if not MUSIC_CACHE["music_files"]:
                conn.logger.bind(tag=TAG).error("Không tìm thấy tệp nhạc nào")
                return
            selected_music = random.choice(MUSIC_CACHE["music_files"])
            music_path = os.path.join(MUSIC_CACHE["music_dir"], selected_music)

        if not os.path.exists(music_path):
            conn.logger.bind(tag=TAG).error(
                f"Tệp nhạc được chọn không tồn tại: {music_path}"
            )
            return
        text = _get_random_play_prompt(selected_music)
        await send_stt_message(conn, text)
        conn.dialogue.put(Message(role="assistant", content=text))

        if conn.intent_type == "intent_llm":
            conn.tts.tts_text_queue.put(
                TTSMessageDTO(
                    sentence_id=conn.sentence_id,
                    sentence_type=SentenceType.FIRST,
                    content_type=ContentType.ACTION,
                )
            )
        conn.tts.tts_text_queue.put(
            TTSMessageDTO(
                sentence_id=conn.sentence_id,
                sentence_type=SentenceType.MIDDLE,
                content_type=ContentType.TEXT,
                content_detail=text,
            )
        )
        conn.tts.tts_text_queue.put(
            TTSMessageDTO(
                sentence_id=conn.sentence_id,
                sentence_type=SentenceType.MIDDLE,
                content_type=ContentType.FILE,
                content_file=music_path,
            )
        )
        if conn.intent_type == "intent_llm":
            conn.tts.tts_text_queue.put(
                TTSMessageDTO(
                    sentence_id=conn.sentence_id,
                    sentence_type=SentenceType.LAST,
                    content_type=ContentType.ACTION,
                )
            )

    except Exception as e:
        conn.logger.bind(tag=TAG).error(f"Phát nhạc thất bại: {str(e)}")
        conn.logger.bind(tag=TAG).error(f"Lỗi chi tiết: {traceback.format_exc()}")
