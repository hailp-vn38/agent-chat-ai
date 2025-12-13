from app.ai.plugins_func.register import (
    register_function,
    ToolType,
    ActionResponse,
    Action,
)
from app.ai.plugins_func.functions.hass_init import initialize_hass_handler
from app.core.logger import setup_logging
import asyncio
import requests

TAG = __name__
logger = setup_logging()

hass_set_state_function_desc = {
    "type": "function",
    "function": {
        "name": "hass_set_state",
        "description": "Thiết lập trạng thái thiết bị trong Home Assistant, bao gồm bật/tắt, điều chỉnh độ sáng đèn, màu sắc, nhiệt độ màu, âm lượng, tạm dừng/tiếp tục và tắt tiếng thiết bị",
        "parameters": {
            "type": "object",
            "properties": {
                "state": {
                    "type": "object",
                    "properties": {
                        "type": {
                            "type": "string",
                            "description": "Hành động cần thực hiện: bật thiết bị: turn_on, tắt thiết bị: turn_off, tăng độ sáng: brightness_up, giảm độ sáng: brightness_down, đặt độ sáng: brightness_value, tăng âm lượng: volume_up, giảm âm lượng: volume_down, đặt âm lượng: volume_set, đặt nhiệt độ màu: set_kelvin, đặt màu: set_color, tạm dừng thiết bị: pause, tiếp tục thiết bị: continue, tắt/bật tiếng: volume_mute",
                        },
                        "input": {
                            "type": "integer",
                            "description": "Chỉ cần khi đặt âm lượng hoặc độ sáng, giá trị hợp lệ 1-100 tương ứng 1%-100%",
                        },
                        "is_muted": {
                            "type": "string",
                            "description": "Chỉ cần khi thực hiện thao tác tắt tiếng; đặt thành true để tắt tiếng, false để bỏ tắt tiếng",
                        },
                        "rgb_color": {
                            "type": "array",
                            "items": {"type": "integer"},
                            "description": "Chỉ cần khi đặt màu, điền giá trị RGB của màu mục tiêu",
                        },
                    },
                    "required": ["type"],
                },
                "entity_id": {
                    "type": "string",
                    "description": "ID thiết bị cần thao tác, entity_id trong Home Assistant",
                },
            },
            "required": ["state", "entity_id"],
        },
    },
}


@register_function("hass_set_state", hass_set_state_function_desc, ToolType.SYSTEM_CTL)
def hass_set_state(conn, entity_id="", state=None):
    if state is None:
        state = {}
    try:
        ha_response = handle_hass_set_state(conn, entity_id, state)
        return ActionResponse(Action.REQLLM, ha_response, None)
    except asyncio.TimeoutError:
        logger.bind(tag=TAG).error(
            "Thiết lập trạng thái Home Assistant quá thời gian chờ"
        )
        return ActionResponse(Action.ERROR, "Yêu cầu quá thời gian chờ", None)
    except Exception:
        error_msg = "Thao tác Home Assistant thất bại"
        logger.bind(tag=TAG).error(error_msg)
        return ActionResponse(Action.ERROR, error_msg, None)


def handle_hass_set_state(conn, entity_id, state):
    ha_config = initialize_hass_handler(conn)
    api_key = ha_config.get("api_key")
    base_url = ha_config.get("base_url")
    """
    state = { "type":"brightness_up","input":"80","is_muted":"true"}
    """
    domains = entity_id.split(".")
    if len(domains) > 1:
        domain = domains[0]
    else:
        return "Thực thi thất bại, ID thiết bị không hợp lệ"
    action = ""
    arg = ""
    value = ""
    if state["type"] == "turn_on":
        description = "Thiết bị đã được bật"
        if domain == "cover":
            action = "open_cover"
        elif domain == "vacuum":
            action = "start"
        else:
            action = "turn_on"
    elif state["type"] == "turn_off":
        description = "Thiết bị đã được tắt"
        if domain == "cover":
            action = "close_cover"
        elif domain == "vacuum":
            action = "stop"
        else:
            action = "turn_off"
    elif state["type"] == "brightness_up":
        description = "Đèn đã được tăng độ sáng"
        action = "turn_on"
        arg = "brightness_step_pct"
        value = 10
    elif state["type"] == "brightness_down":
        description = "Đèn đã được giảm độ sáng"
        action = "turn_on"
        arg = "brightness_step_pct"
        value = -10
    elif state["type"] == "brightness_value":
        description = f"Độ sáng đã được đặt thành {state['input']}"
        action = "turn_on"
        arg = "brightness_pct"
        value = state["input"]
    elif state["type"] == "set_color":
        description = f"Màu sắc đã được đặt thành {state['rgb_color']}"
        action = "turn_on"
        arg = "rgb_color"
        value = state["rgb_color"]
    elif state["type"] == "set_kelvin":
        description = f"Nhiệt độ màu đã được đặt thành {state['input']}K"
        action = "turn_on"
        arg = "kelvin"
        value = state["input"]
    elif state["type"] == "volume_up":
        description = "Âm lượng đã được tăng"
        action = state["type"]
    elif state["type"] == "volume_down":
        description = "Âm lượng đã được giảm"
        action = state["type"]
    elif state["type"] == "volume_set":
        description = f"Âm lượng đã được đặt thành {state['input']}"
        action = state["type"]
        arg = "volume_level"
        value = state["input"]
        if state["input"] >= 1:
            value = state["input"] / 100
    elif state["type"] == "volume_mute":
        description = "Thiết bị đã được tắt tiếng"
        action = state["type"]
        arg = "is_volume_muted"
        value = state["is_muted"]
    elif state["type"] == "pause":
        description = "Thiết bị đã tạm dừng"
        action = state["type"]
        if domain == "media_player":
            action = "media_pause"
        if domain == "cover":
            action = "stop_cover"
        if domain == "vacuum":
            action = "pause"
    elif state["type"] == "continue":
        description = "Thiết bị đã tiếp tục"
        if domain == "media_player":
            action = "media_play"
        if domain == "vacuum":
            action = "start"
    else:
        return f"Tính năng {state['type']} của {domain} hiện chưa được hỗ trợ"

    if arg == "":
        data = {
            "entity_id": entity_id,
        }
    else:
        data = {"entity_id": entity_id, arg: value}
    url = f"{base_url}/api/services/{domain}/{action}"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    response = requests.post(
        url, headers=headers, json=data, timeout=5
    )  # Thiết lập timeout 5 giây
    logger.bind(tag=TAG).info(
        f"Thiết lập trạng thái: {description}, url: {url}, mã phản hồi: {response.status_code}"
    )
    if response.status_code == 200:
        return description
    else:
        return f"Thiết lập thất bại, mã lỗi: {response.status_code}"
