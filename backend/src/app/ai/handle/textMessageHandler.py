from __future__ import annotations
from abc import abstractmethod, ABC
from typing import Dict, Any, TYPE_CHECKING
from app.ai.handle.textMessageType import TextMessageType

if TYPE_CHECKING:
    from app.ai.connection import ConnectionHandler  # chỉ dùng cho hint, không chạy lúc runtime

TAG = __name__


class TextMessageHandler(ABC):
    """Lớp cơ sở trừu tượng cho các trình xử lý thông điệp"""

    @abstractmethod
    async def handle(self, conn: ConnectionHandler, msg_json: Dict[str, Any]) -> None:
        """Phương thức trừu tượng để xử lý thông điệp"""
        pass

    @property
    @abstractmethod
    def message_type(self) -> TextMessageType:
        """Trả về loại thông điệp mà trình xử lý đảm nhiệm"""
        pass
