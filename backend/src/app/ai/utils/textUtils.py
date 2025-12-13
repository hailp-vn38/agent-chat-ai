import json
from typing import Iterable, Optional

TAG = __name__
EMOJI_MAP = {
    "😂": "laughing",
    "😭": "crying",
    "😠": "angry",
    "😔": "sad",
    "😍": "loving",
    "😲": "surprised",
    "😱": "shocked",
    "🤔": "thinking",
    "😌": "relaxed",
    "😴": "sleepy",
    "😜": "silly",
    "🙄": "confused",
    "😶": "neutral",
    "🙂": "happy",
    "😆": "laughing",
    "😳": "embarrassed",
    "😉": "winking",
    "😎": "cool",
    "🤤": "delicious",
    "😘": "kissy",
    "😏": "confident",
}
EMOJI_RANGES = [
    (0x1F600, 0x1F64F),
    (0x1F300, 0x1F5FF),
    (0x1F680, 0x1F6FF),
    (0x1F900, 0x1F9FF),
    (0x1FA70, 0x1FAFF),
    (0x2600, 0x26FF),
    (0x2700, 0x27BF),
]

PUNCTUATION_SET = {
    "，",
    ",",  # Dấu phẩy Trung + Anh
    "。",
    ".",  # Dấu chấm Trung + Anh
    "！",
    "!",  # Dấu chấm than Trung + Anh
    "“",
    "”",
    '"',  # Dấu ngoặc kép Trung + Anh
    "：",
    ":",  # Dấu hai chấm Trung + Anh
    "-",
    "－",  # Gạch nối tiếng Anh + gạch ngang full-width
    "、",  # Dấu ngắt câu tiếng Trung
    "[",
    "]",  # Ngoặc vuông
    "【",
    "】",  # Ngoặc vuông tiếng Trung
}


def get_string_no_punctuation_or_emoji(
    s: str, keep_trailing_punctuations: Optional[Iterable[str]] = None
):
    """Loại bỏ khoảng trắng, dấu câu và emoji ở đầu cuối chuỗi"""
    chars = list(s)
    keep_trailing = (
        set(keep_trailing_punctuations) if keep_trailing_punctuations else None
    )
    # Xử lý ký tự ở phần đầu
    start = 0
    while start < len(chars) and is_punctuation_or_emoji(chars[start]):
        start += 1
    # Xử lý ký tự ở phần cuối
    end = len(chars) - 1
    while end >= start and is_punctuation_or_emoji(chars[end]):
        char = chars[end]
        if keep_trailing and char in keep_trailing:
            break
        end -= 1
    return "".join(chars[start : end + 1])


def is_punctuation_or_emoji(char):
    """Kiểm tra ký tự có phải khoảng trắng, dấu câu chỉ định hoặc emoji"""
    if char.isspace() or char in PUNCTUATION_SET:
        return True
    return is_emoji(char)


async def get_emotion(conn, text):
    """Lấy thông tin cảm xúc trong văn bản"""
    emoji = "🙂"
    emotion = "happy"
    for char in text:
        if char in EMOJI_MAP:
            emoji = char
            emotion = EMOJI_MAP[char]
            break
    try:
        await conn.send_raw(
            json.dumps(
                {
                    "type": "llm",
                    "text": emoji,
                    "emotion": emotion,
                    "session_id": conn.session_id,
                }
            )
        )
    except Exception as e:
        conn.logger.bind(tag=TAG).warning(f"Gửi biểu cảm cảm xúc thất bại, lỗi: {e}")
    return


def is_emoji(char):
    """Kiểm tra ký tự có phải emoji hay không"""
    code_point = ord(char)
    return any(start <= code_point <= end for start, end in EMOJI_RANGES)


def check_emoji(text):
    """Loại bỏ toàn bộ emoji trong văn bản"""
    return ''.join(char for char in text if not is_emoji(char) and char != "\n")
