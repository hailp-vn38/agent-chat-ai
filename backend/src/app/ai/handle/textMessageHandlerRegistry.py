from __future__ import annotations
from typing import Dict, Optional
from app.ai.handle.textHandler.abortMessageHandler import AbortTextMessageHandler
from app.ai.handle.textHandler.helloMessageHandler import HelloTextMessageHandler
from app.ai.handle.textHandler.iotMessageHandler import IotTextMessageHandler
from app.ai.handle.textHandler.listenMessageHandler import ListenTextMessageHandler
from app.ai.handle.textHandler.mcpMessageHandler import McpTextMessageHandler
from app.ai.handle.textMessageHandler import TextMessageHandler
from app.ai.handle.textHandler.serverMessageHandler import ServerTextMessageHandler
from app.ai.handle.textHandler.notificationMessageHandler import (
    NotificationMessageHandler,
)
from app.ai.handle.textHandler.speakMessageHandler import SpeakTextMessageHandler


TAG = __name__


class TextMessageHandlerRegistry:
    """Bảng đăng ký trình xử lý thông điệp"""

    def __init__(self):
        self._handlers: Dict[str, TextMessageHandler] = {}
        self._register_default_handlers()

    def _register_default_handlers(self) -> None:
        """Đăng ký các trình xử lý mặc định"""
        handlers = [
            HelloTextMessageHandler(),
            AbortTextMessageHandler(),
            ListenTextMessageHandler(),
            IotTextMessageHandler(),
            McpTextMessageHandler(),
            ServerTextMessageHandler(),
            NotificationMessageHandler(),
            SpeakTextMessageHandler(),
        ]

        for handler in handlers:
            self.register_handler(handler)

    def register_handler(self, handler: TextMessageHandler) -> None:
        """Đăng ký trình xử lý thông điệp"""
        self._handlers[handler.message_type.value] = handler

    def get_handler(self, message_type: str) -> Optional[TextMessageHandler]:
        """Lấy trình xử lý thông điệp"""
        return self._handlers.get(message_type)

    def get_supported_types(self) -> list:
        """Lấy danh sách loại thông điệp hỗ trợ"""
        return list(self._handlers.keys())
