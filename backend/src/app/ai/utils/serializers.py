"""Utility functions để serialize object thành readable format"""

from typing import Any, Dict
import json
from app.ai.plugins_func.register import ActionResponse


def serialize_object(obj: Any) -> Dict[str, Any]:
    """
    Chuyển đổi object thành dictionary cho logging.

    Args:
        obj: Object cần serialize

    Returns:
        Dictionary biểu diễn object
    """
    if isinstance(obj, ActionResponse):
        return {
            "action": obj.action.name if obj.action else None,
            "action_message": obj.action.message if obj.action else None,
            "result": obj.result,
            "response": obj.response,
        }

    # Nếu là Pydantic model, sử dụng .dict()
    if hasattr(obj, "dict"):
        return obj.dict()

    # Nếu là object thông thường, lấy __dict__
    if hasattr(obj, "__dict__"):
        return obj.__dict__

    # Fallback
    return {"value": str(obj)}


def format_action_response(response: ActionResponse) -> str:
    """
    Format ActionResponse thành string dễ đọc cho logging.

    Args:
        response: ActionResponse object

    Returns:
        String formatted
    """
    data = serialize_object(response)
    return json.dumps(data, ensure_ascii=False, indent=2)
