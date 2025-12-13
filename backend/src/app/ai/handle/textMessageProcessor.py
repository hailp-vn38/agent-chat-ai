from __future__ import annotations
import json
from typing import TYPE_CHECKING
from app.ai.handle.textMessageHandlerRegistry import TextMessageHandlerRegistry

if TYPE_CHECKING:
    from app.ai.connection import (
        ConnectionHandler,
    )  # chỉ dùng cho hint, không chạy lúc runtime


TAG = __name__


class TextMessageProcessor:
    """Lớp xử lý thông điệp chính"""

    def __init__(self, registry: TextMessageHandlerRegistry):
        self.registry = registry

    async def process_message(self, conn: ConnectionHandler, message: str) -> None:
        """Điểm vào chính để xử lý thông điệp"""
        try:
            # Phân tích thông điệp JSON
            msg_json = json.loads(message)

            # Xử lý thông điệp JSON
            if isinstance(msg_json, dict):
                message_type = msg_json.get("type")

                # Ghi log
                conn.logger.bind(tag=TAG).debug(
                    f"Nhận được thông điệp {message_type}: {message}"
                )

                # Lấy và thực thi trình xử lý
                handler = self.registry.get_handler(message_type)
                if handler:
                    await handler.handle(conn, msg_json)
                else:
                    conn.logger.bind(tag=TAG).error(
                        f"Nhận được thông điệp với loại không xác định: {message}"
                    )
            # Xử lý thông điệp là số thuần
            elif isinstance(msg_json, int):
                conn.logger.bind(tag=TAG).debug(
                    f"Nhận được thông điệp dạng số: {message}"
                )
                await conn.send_raw(message)

        except json.JSONDecodeError:
            # Thông điệp không phải JSON sẽ được chuyển tiếp trực tiếp
            conn.logger.bind(tag=TAG).error(f"Phát hiện thông điệp lỗi: {message}")
            await conn.send_raw(message)
