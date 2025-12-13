from __future__ import annotations
from typing import TYPE_CHECKING
from app.ai.handle.textMessageHandlerRegistry import TextMessageHandlerRegistry
from app.ai.handle.textMessageProcessor import TextMessageProcessor

if TYPE_CHECKING:
    from app.ai.connection import ConnectionHandler  # chỉ dùng cho hint, không chạy lúc runtime

TAG = __name__

# Đăng ký trình xử lý toàn cục
message_registry = TextMessageHandlerRegistry()

# Tạo instance xử lý thông điệp toàn cục
message_processor = TextMessageProcessor(message_registry)


async def handleTextMessage(conn: ConnectionHandler, message: str):
    """Xử lý thông điệp văn bản"""
    await message_processor.process_message(conn, message)
