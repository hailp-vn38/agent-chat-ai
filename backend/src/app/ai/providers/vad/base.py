from __future__ import annotations
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from app.ai.connection import ConnectionHandler  # chỉ dùng cho hint, không chạy lúc runtime


class VADProviderBase(ABC):
    @abstractmethod
    def is_vad(self, conn: ConnectionHandler, data: bytes) -> bool:
        """Phát hiện hoạt động giọng nói trong dữ liệu âm thanh"""
        pass
