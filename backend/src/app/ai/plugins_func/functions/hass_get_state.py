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

hass_get_state_function_desc = {
    "type": "function",
    "function": {
        "name": "hass_get_state",
        "description": "Lấy trạng thái thiết bị trong Home Assistant, gồm độ sáng đèn, màu sắc, nhiệt độ màu, âm lượng media và trạng thái tạm dừng/tiếp tục của thiết bị",
        "parameters": {
            "type": "object",
            "properties": {
                "entity_id": {
                    "type": "string",
                    "description": "ID thiết bị cần thao tác, entity_id trong Home Assistant",
                }
            },
            "required": ["entity_id"],
        },
    },
}


@register_function("hass_get_state", hass_get_state_function_desc, ToolType.SYSTEM_CTL)
def hass_get_state(conn, entity_id=""):
    try:
        ha_response = handle_hass_get_state(conn, entity_id)
        return ActionResponse(Action.REQLLM, ha_response, None)
    except asyncio.TimeoutError:
        logger.bind(tag=TAG).error("Lấy trạng thái Home Assistant quá thời gian chờ")
        return ActionResponse(Action.ERROR, "Yêu cầu quá thời gian chờ", None)
    except Exception:
        error_msg = "Thao tác Home Assistant thất bại"
        logger.bind(tag=TAG).error(error_msg)
        return ActionResponse(Action.ERROR, error_msg, None)


def handle_hass_get_state(conn, entity_id):
    ha_config = initialize_hass_handler(conn)
    api_key = ha_config.get("api_key")
    base_url = ha_config.get("base_url")
    url = f"{base_url}/api/states/{entity_id}"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    response = requests.get(url, headers=headers, timeout=5)
    if response.status_code == 200:
        responsetext = "Trạng thái thiết bị: " + response.json()["state"] + " "
        logger.bind(tag=TAG).info(f"Nội dung API trả về: {response.json()}")

        if "media_title" in response.json()["attributes"]:
            responsetext = (
                responsetext
                + "Đang phát: "
                + str(response.json()["attributes"]["media_title"])
                + " "
            )
        if "volume_level" in response.json()["attributes"]:
            responsetext = (
                responsetext
                + "Âm lượng: "
                + str(response.json()["attributes"]["volume_level"])
                + " "
            )
        if "color_temp_kelvin" in response.json()["attributes"]:
            responsetext = (
                responsetext
                + "Nhiệt độ màu: "
                + str(response.json()["attributes"]["color_temp_kelvin"])
                + " "
            )
        if "rgb_color" in response.json()["attributes"]:
            responsetext = (
                responsetext
                + "Màu RGB: "
                + str(response.json()["attributes"]["rgb_color"])
                + " "
            )
        if "brightness" in response.json()["attributes"]:
            responsetext = (
                responsetext
                + "Độ sáng: "
                + str(response.json()["attributes"]["brightness"])
                + " "
            )
        logger.bind(tag=TAG).info(f"Kết quả truy vấn: {responsetext}")
        return responsetext
        # return response.json()['attributes']
        # response.attributes

    else:
        return f"Chuyển đổi thất bại, mã lỗi: {response.status_code}"
