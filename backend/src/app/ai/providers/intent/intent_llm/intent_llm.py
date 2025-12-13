from __future__ import annotations

from typing import List, Dict, TYPE_CHECKING
from ..base import IntentProviderBase
from app.ai.plugins_func.functions.play_music import initialize_music_handler
from app.core.logger import setup_logging
import re
import json
import hashlib
import time

TAG = __name__
logger = setup_logging()


if TYPE_CHECKING:
    from app.ai.connection import (
        ConnectionHandler,
    )  # chỉ dùng cho hint, không chạy lúc runtime


class IntentProvider(IntentProviderBase):
    def __init__(self, config):
        super().__init__(config)
        self.llm = None
        self.promot = ""
        # Nhập bộ quản lý bộ nhớ đệm toàn cục
        from app.ai.utils.cache import async_cache_manager, CacheType

        self.cache_manager = async_cache_manager
        self.CacheType = CacheType
        self.history_count = 4  # Mặc định dùng 4 lượt hội thoại gần nhất

    def get_intent_system_prompt(self, functions_list: str) -> str:
        """
        Tạo prompt hệ thống dựa trên cấu hình ý định và danh sách hàm khả dụng
        Args:
            functions: Chuỗi JSON mô tả danh sách hàm khả dụng
        Returns:
            Prompt hệ thống đã định dạng
        """

        # Xây dựng phần mô tả hàm
        functions_desc = "Danh sách hàm có thể dùng:\n"
        for func in functions_list:
            func_info = func.get("function") or {}
            name = func_info.get("name") or ""
            desc = func_info.get("description") or ""
            params = func_info.get("parameters") or {}

            functions_desc += f"\nTên hàm: {name}\n"
            functions_desc += f"Mô tả: {desc}\n"

            if params:
                functions_desc += "Tham số:\n"
                for param_name, param_info in (params.get("properties") or {}).items():
                    param_desc = param_info.get("description", "")
                    param_type = param_info.get("type", "")
                    functions_desc += f"- {param_name} ({param_type}): {param_desc}\n"

            functions_desc += "---\n"

        prompt = (
            "【YÊU CẦU ĐỊNH DẠNG NGHIÊM NGẶT】Bạn chỉ được phép trả về JSON, tuyệt đối không xuất hiện ngôn ngữ tự nhiên!\n\n"
            "Bạn là trợ lý nhận diện ý định. Hãy phân tích câu cuối cùng của người dùng, xác định ý định và gọi hàm phù hợp.\n\n"
            "【QUY TẮC QUAN TRỌNG】Các truy vấn sau phải trả về result_for_context, không được gọi hàm:\n"
            "- Hỏi thời gian hiện tại (ví dụ: bây giờ mấy giờ, thời gian hiện tại, hỏi thời gian...)\n"
            "- Hỏi ngày hôm nay (ví dụ: hôm nay ngày bao nhiêu, hôm nay là thứ mấy...)\n"
            "- Hỏi âm lịch hôm nay (ví dụ: hôm nay âm lịch bao nhiêu, tiết khí gì...)\n"
            "- Hỏi vị trí hiện tại (ví dụ: tôi đang ở đâu, bạn biết tôi ở thành phố nào không...)\n"
            "Hệ thống sẽ tự xây dựng câu trả lời dựa trên ngữ cảnh.\n\n"
            "- Nếu người dùng dùng từ nghi vấn (như 'làm sao', 'tại sao', 'như thế nào') để hỏi về việc thoát (ví dụ 'sao lại thoát?'), lưu ý đây không phải yêu cầu thoát, hãy trả về {'function_call': {'name': 'continue_chat'}}\n"
            "- Chỉ khi người dùng rõ ràng yêu cầu 'thoát hệ thống', 'kết thúc trò chuyện', 'tôi không muốn nói chuyện nữa'... mới gọi handle_exit_intent\n\n"
            f"{functions_desc}\n"
            "Quy trình xử lý:\n"
            "1. Phân tích đầu vào người dùng, xác định ý định\n"
            "2. Kiểm tra có thuộc các truy vấn cơ bản (thời gian, ngày...) không; nếu có trả về result_for_context\n"
            "3. Chọn hàm phù hợp nhất từ danh sách hàm khả dụng\n"
            "4. Nếu tìm thấy hàm phù hợp, tạo JSON function_call tương ứng\n"
            '5. Nếu không có hàm phù hợp, trả về {"function_call": {"name": "continue_chat"}}\n\n'
            "Yêu cầu định dạng đầu ra:\n"
            "1. Phải là JSON thuần, không có văn bản khác\n"
            "2. Bắt buộc có trường function_call\n"
            "3. function_call phải có trường name\n"
            "4. Nếu hàm cần tham số, phải có trường arguments\n\n"
            "Ví dụ:\n"
            "```\n"
            "Người dùng: Bây giờ mấy giờ?\n"
            'Trả về: {"function_call": {"name": "result_for_context"}}\n'
            "```\n"
            "```\n"
            "Người dùng: Pin hiện tại còn bao nhiêu?\n"
            'Trả về: {"function_call": {"name": "get_battery_level", "arguments": {"response_success": "Pin hiện tại là {value}%", "response_failure": "Không thể lấy phần trăm pin của Battery"}}}\n'
            "```\n"
            "```\n"
            "Người dùng: Độ sáng màn hình hiện tại là bao nhiêu?\n"
            'Trả về: {"function_call": {"name": "self_screen_get_brightness"}}\n'
            "```\n"
            "```\n"
            "Người dùng: Đặt độ sáng màn hình 50%\n"
            'Trả về: {"function_call": {"name": "self_screen_set_brightness", "arguments": {"brightness": 50}}}\n'
            "```\n"
            "```\n"
            "Người dùng: Tôi muốn kết thúc trò chuyện\n"
            'Trả về: {"function_call": {"name": "handle_exit_intent", "arguments": {"say_goodbye": "goodbye"}}}\n'
            "```\n"
            "```\n"
            "Người dùng: Xin chào\n"
            'Trả về: {"function_call": {"name": "continue_chat"}}\n'
            "```\n\n"
            "Lưu ý:\n"
            "1. Chỉ trả về JSON, không thêm văn bản khác\n"
            '2. Luôn kiểm tra xem truy vấn có phải thông tin cơ bản không; nếu đúng trả về {"function_call": {"name": "result_for_context"}} và không cần arguments\n'
            '3. Nếu không có hàm phù hợp, trả về {"function_call": {"name": "continue_chat"}}\n'
            "4. Đảm bảo JSON hợp lệ và đủ các trường cần thiết\n"
            "5. result_for_context không cần tham số, hệ thống tự lấy từ ngữ cảnh\n"
            "Ghi chú đặc biệt:\n"
            "- Khi người dùng nhập nhiều lệnh trong một câu (ví dụ 'bật đèn và tăng âm lượng')\n"
            "- Hãy trả về mảng JSON gồm nhiều function_call\n"
            "- Ví dụ: {'function_calls': [{name:'light_on'}, {name:'volume_up'}]}\n\n"
            "【CẢNH BÁO CUỐI】Tuyệt đối không xuất ra ngôn ngữ tự nhiên, biểu tượng cảm xúc hoặc lời giải thích! Chỉ được phép trả về JSON hợp lệ, vi phạm sẽ gây lỗi hệ thống!"
        )
        return prompt

    def replyResult(self, text: str, original_text: str):
        llm_result = self.llm.response_no_stream(
            system_prompt=text,
            user_prompt="Hãy dựa trên nội dung trên, trả lời người dùng như một con người với giọng tự nhiên, ngắn gọn và đi thẳng vào kết quả. Người dùng đang nói:"
            + original_text,
        )
        return llm_result

    async def detect_intent(
        self, conn: ConnectionHandler, dialogue_history: List[Dict], text: str
    ) -> str:
        if not self.llm:
            raise ValueError("LLM provider not set")
        if conn.func_handler is None:
            return '{"function_call": {"name": "continue_chat"}}'

        # Ghi nhận thời gian bắt đầu tổng thể
        total_start_time = time.time()

        # In thông tin mô hình được sử dụng
        model_info = getattr(self.llm, "model_name", str(self.llm.__class__.__name__))
        logger.bind(tag=TAG).debug(f"Dùng mô hình nhận diện ý định: {model_info}")

        # Tính khóa bộ nhớ đệm - dùng MAC address (string) thay vì UUID
        device_identifier = getattr(conn, "device_mac_address", None) or str(
            conn.device_id or "unknown"
        )
        cache_key = hashlib.md5((device_identifier + text).encode()).hexdigest()

        # Kiểm tra bộ nhớ đệm
        cached_intent = await self.cache_manager.get(self.CacheType.INTENT, cache_key)
        if cached_intent is not None:
            cache_time = time.time() - total_start_time
            logger.bind(tag=TAG).debug(
                f"Dùng ý định từ bộ nhớ đệm: {cache_key} -> {cached_intent}, mất {cache_time:.4f}s"
            )
            return cached_intent

        if self.promot == "":
            functions = conn.func_handler.get_functions()
            if hasattr(conn, "mcp_client"):
                mcp_tools = conn.mcp_client.get_available_tools()
                if mcp_tools is not None and len(mcp_tools) > 0:
                    if functions is None:
                        functions = []
                    functions.extend(mcp_tools)

            self.promot = self.get_intent_system_prompt(functions)

        music_config = initialize_music_handler(conn)
        music_file_names = music_config["music_file_names"]
        prompt_music = f"{self.promot}\n<musicNames>{music_file_names}\n</musicNames>"

        home_assistant_cfg = conn.config["plugins"].get("home_assistant")
        if home_assistant_cfg:
            devices = home_assistant_cfg.get("devices", [])
        else:
            devices = []
        if len(devices) > 0:
            hass_prompt = "\nDưới đây là danh sách thiết bị thông minh trong nhà tôi (vị trí, tên, entity_id), có thể điều khiển qua Home Assistant\n"
            for device in devices:
                hass_prompt += device + "\n"
            prompt_music += hass_prompt

        logger.bind(tag=TAG).debug(f"User prompt: {prompt_music}")

        # Xây dựng prompt lịch sử hội thoại
        msgStr = ""

        # Lấy các đoạn hội thoại gần nhất
        start_idx = max(0, len(dialogue_history) - self.history_count)
        for i in range(start_idx, len(dialogue_history)):
            msgStr += f"{dialogue_history[i].role}: {dialogue_history[i].content}\n"

        msgStr += f"User: {text}\n"
        user_prompt = f"current dialogue:\n{msgStr}"

        # Ghi nhận thời gian hoàn tất tiền xử lý
        preprocess_time = time.time() - total_start_time
        logger.bind(tag=TAG).debug(
            f"Tiền xử lý cho nhận diện ý định mất: {preprocess_time:.4f}s"
        )

        # Sử dụng LLM để nhận diện ý định
        llm_start_time = time.time()
        logger.bind(tag=TAG).debug(
            f"Bắt đầu gọi LLM nhận diện ý định, mô hình: {model_info}"
        )

        intent = self.llm.response_no_stream(
            system_prompt=prompt_music, user_prompt=user_prompt
        )

        # Ghi nhận thời gian hoàn tất gọi LLM
        llm_time = time.time() - llm_start_time
        logger.bind(tag=TAG).debug(
            f"LLM nhận diện ý định xong, mô hình: {model_info}, thời gian gọi: {llm_time:.4f}s"
        )

        # Bắt đầu ghi nhận thời gian hậu xử lý
        postprocess_start_time = time.time()

        # Làm sạch và phân tích phản hồi
        intent = intent.strip()
        # Thử trích phần JSON
        match = re.search(r"\{.*\}", intent, re.DOTALL)
        if match:
            intent = match.group(0)

        # Ghi nhận tổng thời gian xử lý
        total_time = time.time() - total_start_time
        logger.bind(tag=TAG).debug(
            f"[Hiệu năng nhận diện ý định] Mô hình: {model_info}, tổng thời gian: {total_time:.4f}s, LLM: {llm_time:.4f}s, truy vấn: '{text[:20]}...'"
        )

        # Thử phân tích thành JSON
        try:
            intent_data = json.loads(intent)
            # Nếu có function_call, chuẩn hóa về định dạng cần xử lý
            if "function_call" in intent_data:
                function_data = intent_data["function_call"]
                function_name = function_data.get("name")
                function_args = function_data.get("arguments") or {}

                # Ghi log hàm đã được nhận diện
                logger.bind(tag=TAG).info(
                    f"LLM nhận diện ý định: {function_name}, tham số: {function_args}"
                )

                # Xử lý các dạng ý định khác nhau
                if function_name == "result_for_context":
                    # Xử lý truy vấn thông tin cơ bản bằng dữ liệu ngữ cảnh
                    logger.bind(tag=TAG).info(
                        "Phát hiện ý định result_for_context, sẽ trả lời trực tiếp từ ngữ cảnh"
                    )

                elif function_name == "continue_chat":
                    # Xử lý hội thoại thông thường
                    # Giữ lại các tin nhắn không liên quan tới công cụ
                    clean_history = [
                        msg
                        for msg in conn.dialogue.dialogue
                        if msg.role not in ["tool", "function"]
                    ]
                    conn.dialogue.dialogue = clean_history

                else:
                    # Xử lý gọi hàm
                    logger.bind(tag=TAG).info(
                        f"Phát hiện ý định gọi hàm: {function_name}"
                    )

            # Lưu vào bộ nhớ đệm và phản hồi
            await self.cache_manager.set(self.CacheType.INTENT, cache_key, intent)
            postprocess_time = time.time() - postprocess_start_time
            logger.bind(tag=TAG).debug(f"Hậu xử lý ý định mất: {postprocess_time:.4f}s")
            return intent
        except json.JSONDecodeError:
            # Thời gian hậu xử lý khi lỗi
            postprocess_time = time.time() - postprocess_start_time
            logger.bind(tag=TAG).error(
                f"Không thể phân tích JSON ý định: {intent}, hậu xử lý mất: {postprocess_time:.4f}s"
            )
            # Nếu phân tích thất bại, mặc định tiếp tục trò chuyện
            return '{"function_call": {"name": "continue_chat"}}'
