from __future__ import annotations
from typing import TYPE_CHECKING

from abc import ABC, abstractmethod
from typing import List, Dict
from app.core.logger import setup_logging

if TYPE_CHECKING:
    from app.ai.connection import ConnectionHandler  # chỉ dùng cho hint, không chạy lúc runtime


TAG = __name__
logger = setup_logging()


class IntentProviderBase(ABC):
    def __init__(self, config):
        self.config = config

    def set_llm(self, llm):
        self.llm = llm
        # Lấy tên và loại mô hình
        model_name = getattr(llm, "model_name", str(llm.__class__.__name__))
        # Ghi log chi tiết hơn
        logger.bind(tag=TAG).info(f"Thiết lập LLM cho nhận diện ý định: {model_name}")

    @abstractmethod
    async def detect_intent(self, conn: ConnectionHandler, dialogue_history: List[Dict], text: str) -> str:
        """
        Phát hiện ý định trong câu nói cuối của người dùng
        Args:
            dialogue_history: Danh sách lịch sử hội thoại, mỗi bản ghi gồm role và content
        Returns:
            Chuỗi thể hiện ý định, theo định dạng:
            - "tiếp tục trò chuyện"
            - "kết thúc trò chuyện"
            - "phát nhạc TÊN_BÀI_HÁT" hoặc "phát nhạc ngẫu nhiên"
            - "tra cứu thời tiết TÊN_ĐỊA ĐIỂM" hoặc "tra cứu thời tiết [vị trí hiện tại]"
        """
        pass
