"""
Mô-đun quản lý prompt hệ thống
Phụ trách quản lý và cập nhật prompt hệ thống, bao gồm khởi tạo nhanh và tăng cường bất đồng bộ
"""

import os
from typing import Dict, Any
from app.core.logger import setup_logging
from jinja2 import Template
from app.ai.utils.paths import get_agent_base_prompt_file


TAG = __name__

WEEKDAY_MAP = {
    "Monday": "Thứ Hai",
    "Tuesday": "Thứ Ba",
    "Wednesday": "Thứ Tư",
    "Thursday": "Thứ Năm",
    "Friday": "Thứ Sáu",
    "Saturday": "Thứ Bảy",
    "Sunday": "Chủ Nhật",
}

EMOJI_List = [
    "😶",
    "🙂",
    "😆",
    "😂",
    "😔",
    "😠",
    "😭",
    "😍",
    "😳",
    "😲",
    "😱",
    "🤔",
    "😉",
    "😎",
    "😌",
    "🤤",
    "😘",
    "😏",
    "😴",
    "😜",
    "🙄",
]


class PromptManager:
    """Trình quản lý prompt hệ thống, phụ trách quản lý và cập nhật prompt"""

    def __init__(self, config: Dict[str, Any], logger=None):
        self.config = config
        self.logger = logger or setup_logging()
        self.base_prompt_template = None
        self.last_update_time = 0

        # Nhập trình quản lý bộ nhớ đệm toàn cục
        from app.ai.utils.cache import async_cache_manager, CacheType

        self.cache_manager = async_cache_manager
        self.CacheType = CacheType

        # Don't call async method from __init__
        self.base_prompt_template = None

    async def _load_base_template(self):
        """Tải template prompt cơ bản"""
        try:
            # Xây dựng đường dẫn tuyệt đối tới file từ thư mục app
            template_path = get_agent_base_prompt_file()
            cache_key = f"prompt_template:{template_path}"

            # Luôn đọc từ file (không cache) để development không bị cache cũ
            if os.path.exists(template_path):
                with open(template_path, "r", encoding="utf-8") as f:
                    template_content = f.read()

                self.base_prompt_template = template_content
                self.logger.bind(tag=TAG).debug("Đã tải template prompt cơ bản từ file")
            else:
                self.logger.bind(tag=TAG).warning(
                    f"Không tìm thấy tệp agent-base-prompt.txt tại {template_path}"
                )
        except Exception as e:
            self.logger.bind(tag=TAG).error(f"Tải template prompt thất bại: {e}")

    async def get_quick_prompt(self, user_prompt: str, device_id: str = None) -> str:
        """Lấy nhanh prompt hệ thống (dùng cấu hình của người dùng)"""
        # Kiểm tra user_prompt có hợp lệ không
        if not user_prompt or not isinstance(user_prompt, str):
            self.logger.bind(tag=TAG).warning(
                f"Prompt không hợp lệ: {user_prompt}, sử dụng prompt mặc định rỗng"
            )
            return ""

        if device_id:
            device_cache_key = f"device_prompt:{device_id}"
            cached_device_prompt = await self.cache_manager.get(
                self.CacheType.DEVICE_PROMPT, device_cache_key
            )
            if cached_device_prompt is not None:
                self.logger.bind(tag=TAG).debug(
                    f"Dùng prompt đã lưu trong cache cho thiết bị {device_id}"
                )
                return cached_device_prompt
            else:
                self.logger.bind(tag=TAG).debug(
                    f"Thiết bị {device_id} không có prompt trong cache, dùng prompt được truyền vào"
                )
                # Lưu cache với type chính xác
                await self.cache_manager.set(
                    self.CacheType.DEVICE_PROMPT, device_cache_key, user_prompt
                )
                self.logger.bind(tag=TAG).debug(
                    f"Đã lưu prompt của thiết bị {device_id} vào cache"
                )

        self.logger.bind(tag=TAG).debug(f"Sử dụng prompt nhanh: {user_prompt[:50]}...")
        return user_prompt

    def _get_current_time_info(self) -> tuple:
        """Lấy thông tin thời gian hiện tại"""
        from .current_time import get_current_date, get_current_weekday

        today_date = get_current_date()
        today_weekday = get_current_weekday()

        return today_date, today_weekday

    async def _get_location_info(self, client_ip: str) -> str:
        """Lấy thông tin vị trí"""
        try:
            if not client_ip or client_ip == "unknown":
                return "Vị trí chưa xác định"

            cache_key = client_ip or "unknown_ip"
            # Lấy từ bộ nhớ đệm trước
            cached_location = await self.cache_manager.get(
                self.CacheType.LOCATION, cache_key
            )
            if cached_location is not None:
                return cached_location

            # Nếu không có trong bộ nhớ đệm, gọi API
            from app.ai.utils.util import get_ip_info

            ip_info = await get_ip_info(client_ip, self.logger)
            city = ip_info.get("city", "Vị trí chưa xác định")
            location = f"{city}"

            # Lưu vào bộ nhớ đệm
            await self.cache_manager.set(self.CacheType.LOCATION, cache_key, location)
            return location
        except Exception as e:
            self.logger.bind(tag=TAG).error(f"Lấy thông tin vị trí thất bại: {e}")
            return "Vị trí chưa xác định"

    async def _get_weather_info(self, conn, location: str) -> str:
        """Lấy thông tin thời tiết"""
        try:
            # Lấy từ bộ nhớ đệm trước
            cached_weather = await self.cache_manager.get(
                self.CacheType.WEATHER, location
            )
            if cached_weather is not None:
                return cached_weather

            # Nếu không có thì gọi hàm get_weather
            from app.ai.plugins_func.functions.get_weather import get_weather
            from app.ai.plugins_func.register import ActionResponse

            # Gọi hàm get_weather
            result = await get_weather(conn, location=location, lang="vi_VN")
            if isinstance(result, ActionResponse):
                weather_report = result.result
                await self.cache_manager.set(
                    self.CacheType.WEATHER, location, weather_report
                )
                return weather_report
            return "Không lấy được thông tin thời tiết"

        except Exception as e:
            self.logger.bind(tag=TAG).error(f"Lấy thông tin thời tiết thất bại: {e}")
            return "Không lấy được thông tin thời tiết"

    async def update_context_info(self, conn, client_ip: str):
        """Cập nhật đồng bộ thông tin ngữ cảnh"""
        try:
            # Lấy thông tin vị trí (dùng bộ nhớ đệm toàn cục)
            local_address = await self._get_location_info(client_ip)
            # Lấy thông tin thời tiết (dùng bộ nhớ đệm toàn cục)
            # await self._get_weather_info(conn, local_address)
            self.logger.bind(tag=TAG).info("Hoàn tất cập nhật thông tin ngữ cảnh")

        except Exception as e:
            self.logger.bind(tag=TAG).error(
                f"Cập nhật thông tin ngữ cảnh thất bại: {e}"
            )

    async def build_enhanced_prompt(
        self,
        user_prompt: str,
        device_id: str,
        client_ip: str = None,
        user_profile: str = None,
        *args,
        **kwargs,
    ) -> str:
        """Xây dựng prompt hệ thống được tăng cường"""
        # Lazy load template if not loaded yet
        if self.base_prompt_template is None:
            await self._load_base_template()

        if not self.base_prompt_template:
            return user_prompt

        try:
            # Lấy thông tin thời gian mới nhất (không lưu cache)
            today_date, today_weekday = self._get_current_time_info()

            # Lấy thông tin ngữ cảnh đã lưu
            local_address = ""
            weather_info = ""

            if client_ip:
                # Lấy thông tin vị trí (từ cache toàn cục)
                local_address = (
                    await self.cache_manager.get(
                        self.CacheType.LOCATION, client_ip or "unknown_ip"
                    )
                    or ""
                )

                # Lấy thông tin thời tiết (từ cache toàn cục)
                if local_address:
                    weather_info = (
                        await self.cache_manager.get(
                            self.CacheType.WEATHER, local_address
                        )
                        or ""
                    )

            # Thay thế biến trong template
            from .current_time import get_current_time

            current_time = get_current_time()

            template = Template(self.base_prompt_template)
            enhanced_prompt = template.render(
                base_prompt=user_prompt,
                current_time=current_time,
                today_date=today_date,
                today_weekday=today_weekday,
                local_address=local_address,
                weather_info=weather_info,
                emojiList=EMOJI_List,
                device_id=device_id,
                user_profile=user_profile,
                *args,
                **kwargs,
            )
            device_cache_key = f"device_prompt:{device_id}"
            await self.cache_manager.set(
                self.CacheType.DEVICE_PROMPT, device_cache_key, enhanced_prompt
            )
            return enhanced_prompt

        except Exception as e:
            self.logger.bind(tag=TAG).error(f"Xây dựng prompt nâng cao thất bại: {e}")
            return user_prompt
