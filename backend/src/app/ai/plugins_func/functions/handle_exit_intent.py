from app.ai.plugins_func.register import (
    register_function,
    ToolType,
    ActionResponse,
    Action,
)
from app.core.logger import setup_logging

TAG = __name__
logger = setup_logging()

handle_exit_intent_function_desc = {
    "type": "function",
    "function": {
        "name": "handle_exit_intent",
        "description": "Được gọi khi người dùng muốn kết thúc cuộc trò chuyện hoặc thoát khỏi hệ thống",
        "parameters": {
            "type": "object",
            "properties": {
                "say_goodbye": {
                    "type": "string",
                    "description": "Lời tạm biệt thân thiện để kết thúc trò chuyện với người dùng",
                }
            },
            "required": ["say_goodbye"],
        },
    },
}


@register_function(
    "handle_exit_intent", handle_exit_intent_function_desc, ToolType.SYSTEM_CTL
)
def handle_exit_intent(conn, say_goodbye: str | None = None):
    # Xử lý ý định thoát
    try:
        if say_goodbye is None:
            say_goodbye = "Tạm biệt, chúc bạn một ngày tốt lành!"
        conn.close_after_chat = True
        logger.bind(tag=TAG).info(f"Đã xử lý ý định thoát: {say_goodbye}")
        return ActionResponse(
            action=Action.RESPONSE,
            result="Ý định thoát đã được xử lý",
            response=say_goodbye,
        )
    except Exception as e:
        logger.bind(tag=TAG).error(f"Lỗi khi xử lý ý định thoát: {e}")
        return ActionResponse(
            action=Action.NONE, result="Xử lý ý định thoát thất bại", response=""
        )
