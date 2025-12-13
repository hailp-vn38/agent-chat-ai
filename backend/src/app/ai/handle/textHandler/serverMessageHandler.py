from __future__ import annotations
import json
from typing import TYPE_CHECKING, Dict, Any
from app.ai.handle.textMessageHandler import TextMessageHandler
from app.ai.handle.textMessageType import TextMessageType

if TYPE_CHECKING:
    from app.ai.connection import ConnectionHandler  # chỉ dùng cho hint, không chạy lúc runtime


TAG = __name__


class ServerTextMessageHandler(TextMessageHandler):
    """Trình xử lý thông điệp MCP"""

    @property
    def message_type(self) -> TextMessageType:
        return TextMessageType.SERVER

    async def handle(self, conn: ConnectionHandler, msg_json: Dict[str, Any]) -> None:
        # Nếu cấu hình được đọc từ API thì phải xác minh secret
        if not conn.read_config_from_api:
            return
        # Lấy secret từ yêu cầu post
        post_secret = msg_json.get("content", {}).get("secret", "")
        secret = conn.config["manager-api"].get("secret", "")
        # Nếu secret không khớp thì trả về
        if post_secret != secret:
            await conn.send_raw(
                json.dumps(
                    {
                        "type": "server",
                        "status": "error",
                        "message": "Xác thực khóa máy chủ thất bại",
                    }
                )
            )
            return
        # Cập nhật cấu hình động
        if msg_json["action"] == "update_config":
            try:
                # Cập nhật cấu hình WebSocketServer
                if not conn.server:
                    await conn.send_raw(
                        json.dumps(
                            {
                                "type": "server",
                                "status": "error",
                                "message": "Không thể lấy phiên bản máy chủ",
                                "content": {"action": "update_config"},
                            }
                        )
                    )
                    return

                if not await conn.server.update_config():
                    await conn.send_raw(
                        json.dumps(
                            {
                                "type": "server",
                                "status": "error",
                                "message": "Cập nhật cấu hình máy chủ thất bại",
                                "content": {"action": "update_config"},
                            }
                        )
                    )
                    return

                # Gửi phản hồi thành công
                await conn.send_raw(
                    json.dumps(
                        {
                            "type": "server",
                            "status": "success",
                            "message": "Cập nhật cấu hình thành công",
                            "content": {"action": "update_config"},
                        }
                    )
                )
            except Exception as e:
                conn.logger.bind(tag=TAG).debug(
                    f"Cập nhật cấu hình thất bại (đã báo lại cho client): {str(e)}"
                )
                await conn.send_raw(
                    json.dumps(
                        {
                            "type": "server",
                            "status": "error",
                            "message": f"Cập nhật cấu hình thất bại: {str(e)}",
                            "content": {"action": "update_config"},
                        }
                    )
                )
        # Khởi động lại máy chủ
        elif msg_json["action"] == "restart":
            await conn.handle_restart(msg_json)
