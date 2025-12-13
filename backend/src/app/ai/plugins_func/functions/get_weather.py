import requests
from bs4 import BeautifulSoup
from app.core.logger import setup_logging
from app.ai.plugins_func.register import (
    register_function,
    ToolType,
    ActionResponse,
    Action,
)
from app.ai.utils.util import get_ip_info

TAG = __name__
logger = setup_logging()

GET_WEATHER_FUNCTION_DESC = {
    "type": "function",
    "function": {
        "name": "get_weather",
        "description": (
            "Lấy thời tiết của một địa điểm; người dùng nên cung cấp vị trí, ví dụ nói 'thời tiết Hàng Châu' thì tham số là 'Hangzhou'."
            "Nếu người dùng cung cấp tên tỉnh, mặc định dùng thành phố thủ phủ. Nếu người dùng nêu một địa danh không phải tỉnh hay thành phố, mặc định dùng thủ phủ tỉnh nơi địa danh thuộc về."
            "Nếu người dùng không chỉ rõ địa điểm mà hỏi chung chung như 'thời tiết thế nào', tham số location để trống."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "location": {
                    "type": "string",
                    "description": "Tên địa điểm, ví dụ Hangzhou. Tham số tùy chọn, nếu không cung cấp thì bỏ trống",
                },
                "lang": {
                    "type": "string",
                    "description": "Trả về mã ngôn ngữ người dùng sử dụng, ví dụ zh_CN/zh_HK/en_US/ja_JP, mặc định zh_CN",
                },
            },
            "required": ["lang"],
        },
    },
}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/92.0.4515.107 Safari/537.36"
    )
}

# Mã thời tiết https://dev.qweather.com/docs/resource/icons/#weather-icons
WEATHER_CODE_MAP = {
    "100": "Trời quang",
    "101": "Nhiều mây",
    "102": "Ít mây",
    "103": "Nắng xen mây",
    "104": "U ám",
    "150": "Trời quang",
    "151": "Nhiều mây",
    "152": "Ít mây",
    "153": "Nắng xen mây",
    "300": "Mưa rào",
    "301": "Mưa rào to",
    "302": "Mưa dông",
    "303": "Mưa dông lớn",
    "304": "Mưa dông kèm mưa đá",
    "305": "Mưa nhỏ",
    "306": "Mưa vừa",
    "307": "Mưa to",
    "308": "Mưa cực lớn",
    "309": "Mưa phùn/nhẹ",
    "310": "Mưa bão",
    "311": "Mưa bão lớn",
    "312": "Mưa bão rất lớn",
    "313": "Mưa đông lạnh",
    "314": "Mưa nhỏ đến vừa",
    "315": "Mưa vừa đến to",
    "316": "Mưa to đến mưa bão",
    "317": "Mưa bão đến mưa bão lớn",
    "318": "Mưa bão lớn đến mưa cực lớn",
    "350": "Mưa rào",
    "351": "Mưa rào to",
    "399": "Mưa",
    "400": "Tuyết nhẹ",
    "401": "Tuyết vừa",
    "402": "Tuyết dày",
    "403": "Bão tuyết",
    "404": "Mưa tuyết",
    "405": "Thời tiết mưa tuyết",
    "406": "Mưa rào kèm tuyết",
    "407": "Tuyết rào",
    "408": "Tuyết nhẹ đến vừa",
    "409": "Tuyết vừa đến dày",
    "410": "Tuyết dày đến bão tuyết",
    "456": "Mưa rào kèm tuyết",
    "457": "Tuyết rào",
    "499": "Tuyết",
    "500": "Sương mỏng",
    "501": "Sương mù",
    "502": "Sương mù dày",
    "503": "Cát bay",
    "504": "Bụi mịn",
    "507": "Bão cát",
    "508": "Bão cát mạnh",
    "509": "Sương mù đặc",
    "510": "Sương mù đặc dày",
    "511": "Sương mù ô nhiễm mức vừa",
    "512": "Sương mù ô nhiễm nặng",
    "513": "Sương mù ô nhiễm nghiêm trọng",
    "514": "Sương mù dày",
    "515": "Sương mù đặc cực mạnh",
    "900": "Nóng",
    "901": "Lạnh",
    "999": "Không xác định",
}


def fetch_city_info(location, api_key, api_host):
    url = f"https://{api_host}/geo/v2/city/lookup?key={api_key}&location={location}&lang=zh"
    response = requests.get(url, headers=HEADERS).json()
    if response.get("error") is not None:
        logger.bind(tag=TAG).error(
            f"Lấy thời tiết thất bại, lý do: {response.get('error', {}).get('detail')}"
        )
        return None
    return response.get("location", [])[0] if response.get("location") else None


def fetch_weather_page(url):
    response = requests.get(url, headers=HEADERS)
    return BeautifulSoup(response.text, "html.parser") if response.ok else None


def parse_weather_info(soup):
    city_name = soup.select_one("h1.c-submenu__location").get_text(strip=True)

    current_abstract = soup.select_one(".c-city-weather-current .current-abstract")
    current_abstract = (
        current_abstract.get_text(strip=True) if current_abstract else "Không xác định"
    )

    current_basic = {}
    for item in soup.select(
        ".c-city-weather-current .current-basic .current-basic___item"
    ):
        parts = item.get_text(strip=True, separator=" ").split(" ")
        if len(parts) == 2:
            key, value = parts[1], parts[0]
            current_basic[key] = value

    temps_list = []
    for row in soup.select(".city-forecast-tabs__row")[
        :7
    ]:  # Lấy dữ liệu 7 ngày đầu tiên
        date = row.select_one(".date-bg .date").get_text(strip=True)
        weather_code = (
            row.select_one(".date-bg .icon")["src"].split("/")[-1].split(".")[0]
        )
        weather = WEATHER_CODE_MAP.get(weather_code, "Không xác định")
        temps = [span.get_text(strip=True) for span in row.select(".tmp-cont .temp")]
        high_temp, low_temp = (temps[0], temps[-1]) if len(temps) >= 2 else (None, None)
        temps_list.append((date, weather, high_temp, low_temp))

    return city_name, current_abstract, current_basic, temps_list


@register_function("get_weather", GET_WEATHER_FUNCTION_DESC, ToolType.SYSTEM_CTL)
async def get_weather(conn, location: str = None, lang: str = "zh_CN"):
    from app.ai.utils.cache import async_cache_manager, CacheType

    api_host = conn.config["plugins"]["get_weather"].get(
        "api_host", "mj7p3y7naa.re.qweatherapi.com"
    )
    api_key = conn.config["plugins"]["get_weather"].get(
        "api_key", "a861d0d5e7bf4ee1a83d9a9e4f96d4da"
    )
    default_location = conn.config["plugins"]["get_weather"]["default_location"]
    client_ip = conn.client_ip

    # Ưu tiên dùng tham số location do người dùng cung cấp
    if not location:
        # Dựa trên IP của client để suy ra thành phố
        if client_ip:
            # Lấy thông tin thành phố của IP từ bộ nhớ đệm
            cached_ip_info = await async_cache_manager.get(CacheType.IP_INFO, client_ip)
            if cached_ip_info:
                location = cached_ip_info.get("city")
            else:
                # Nếu không có trong bộ nhớ đệm thì gọi API để lấy
                ip_info = await get_ip_info(client_ip, logger)
                if ip_info:
                    await async_cache_manager.set(CacheType.IP_INFO, client_ip, ip_info)
                    location = ip_info.get("city")

            if not location:
                location = default_location
        else:
            # Nếu không có IP thì dùng vị trí mặc định
            location = default_location
    # Thử lấy báo cáo thời tiết đầy đủ từ bộ nhớ đệm
    weather_cache_key = f"full_weather_{location}_{lang}"
    cached_weather_report = await async_cache_manager.get(
        CacheType.WEATHER, weather_cache_key
    )
    if cached_weather_report:
        return ActionResponse(Action.REQLLM, cached_weather_report, None)

    # Nếu không có trong bộ nhớ đệm thì lấy dữ liệu thời tiết thời gian thực
    city_info = fetch_city_info(location, api_key, api_host)
    if not city_info:
        return ActionResponse(
            Action.REQLLM,
            f"Không tìm thấy thành phố liên quan: {location}, vui lòng kiểm tra địa điểm",
            None,
        )
    soup = fetch_weather_page(city_info["fxLink"])
    if not soup:
        return ActionResponse(Action.REQLLM, None, "Yêu cầu thất bại")
    city_name, current_abstract, current_basic, temps_list = parse_weather_info(soup)

    weather_report = f"Địa điểm bạn tra cứu là: {city_name}\n\nThời tiết hiện tại: {current_abstract}\n"

    # Thêm các tham số thời tiết hiện tại hợp lệ
    if current_basic:
        weather_report += "Thông số chi tiết:\n"
        for key, value in current_basic.items():
            if value != "0":  # Lọc giá trị không hợp lệ
                weather_report += f"  · {key}: {value}\n"

    # Thêm dự báo 7 ngày
    weather_report += "\nDự báo 7 ngày tới:\n"
    for date, weather, high, low in temps_list:
        weather_report += f"{date}: {weather}, nhiệt độ {low}~{high}\n"

    # Thông báo nhắc người dùng
    weather_report += (
        "\n(Nếu cần thời tiết cụ thể của ngày nào, hãy cho tôi biết ngày đó)"
    )

    # Lưu toàn bộ báo cáo thời tiết vào bộ nhớ đệm
    await async_cache_manager.set(CacheType.WEATHER, weather_cache_key, weather_report)

    return ActionResponse(Action.REQLLM, weather_report, None)
