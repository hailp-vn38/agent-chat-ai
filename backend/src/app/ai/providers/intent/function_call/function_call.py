from __future__ import annotations
from ..base import IntentProviderBase
from typing import List, Dict,TYPE_CHECKING
from app.core.logger import setup_logging

TAG = __name__
logger = setup_logging()

if TYPE_CHECKING:
    from app.ai.connection import ConnectionHandler  # chỉ dùng cho hint, không chạy lúc runtime

class IntentProvider(IntentProviderBase):
    async def detect_intent(self, conn: ConnectionHandler, dialogue_history: List[Dict], text: str) -> str:
        """
        Triển khai nhận diện ý định mặc định, luôn trả về tiếp tục trò chuyện
        Args:
            dialogue_history: Danh sách lịch sử đối thoại
            text: Nội dung đối thoại hiện tại
        Returns:
            Luôn trả về chuỗi JSON gọi continue_chat
        """
        logger.bind(tag=TAG).debug("Using functionCallProvider, always returning continue chat")
        return '{"function_call": {"name": "continue_chat"}}'
