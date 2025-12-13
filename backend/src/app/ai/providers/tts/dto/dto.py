from enum import Enum
from typing import Optional


class SentenceType(Enum):
    # Giai đoạn phát lời
    FIRST = "FIRST"  # Câu đầu tiên
    MIDDLE = "MIDDLE"  # Đang nói
    LAST = "LAST"  # Câu cuối cùng


class ContentType(Enum):
    # Loại nội dung
    TEXT = "TEXT"  # Nội dung văn bản
    FILE = "FILE"  # Nội dung file
    ACTION = "ACTION"  # Nội dung hành động


class InterfaceType(Enum):
    # Kiểu giao tiếp
    DUAL_STREAM = "DUAL_STREAM"  # Song luồng
    SINGLE_STREAM = "SINGLE_STREAM"  # Đơn luồng
    NON_STREAM = "NON_STREAM"  # Không luồng


class TTSMessageDTO:
    def __init__(
        self,
        sentence_id: str,
        # Giai đoạn phát lời
        sentence_type: SentenceType,
        # Loại nội dung
        content_type: ContentType,
        # Chi tiết nội dung, thường là văn bản cần chuyển hoặc lời bài hát
        content_detail: Optional[str] = None,
        # Nếu là nội dung dạng file, truyền đường dẫn file
        content_file: Optional[str] = None,
    ):
        self.sentence_id = sentence_id
        self.sentence_type = sentence_type
        self.content_type = content_type
        self.content_detail = content_detail
        self.content_file = content_file
