import os, json, uuid
from types import SimpleNamespace
from typing import Any, Dict, List

from google import generativeai as genai
from google.generativeai import types, GenerationConfig

from app.ai.providers.llm.base import LLMProviderBase
from app.ai.utils.util import check_model_key
from app.core.logger import setup_logging
from google.generativeai.types import GenerateContentResponse
from requests import RequestException

log = setup_logging()
TAG = __name__


class LLMProvider(LLMProviderBase):
    def __init__(self, cfg: Dict[str, Any]):
        self.model_name = cfg.get("model_name", "gemini-2.0-flash")
        self.api_key = cfg["api_key"]
        http_proxy = cfg.get("http_proxy")
        https_proxy = cfg.get("https_proxy")

        model_key_msg = check_model_key("LLM", self.api_key)
        if model_key_msg:
            log.bind(tag=TAG).error(model_key_msg)

        if http_proxy or https_proxy:
            log.bind(tag=TAG).info(
                f"Phát hiện cấu hình proxy Gemini, bắt đầu kiểm tra kết nối proxy và cấu hình môi trường..."
            )
            log.bind(tag=TAG).info(
                f"Cấu hình proxy Gemini thành công - HTTP: {http_proxy}, HTTPS: {https_proxy}"
            )
        # Cấu hình khóa API
        genai.configure(api_key=self.api_key)

        # Đặt timeout yêu cầu (giây)
        self.timeout = cfg.get("timeout", 120)  # Mặc định 120 giây

        # 创建模型实例
        self.model = genai.GenerativeModel(self.model_name)

        self.gen_cfg = GenerationConfig(
            temperature=0.7,
            top_p=0.9,
            top_k=40,
            max_output_tokens=2048,
        )

    @staticmethod
    def _sanitize_schema(schema: Dict[str, Any]) -> Dict[str, Any]:
        """
        Loại bỏ các trường không được hỗ trợ từ JSON schema cho Gemini API.
        Gemini chỉ hỗ trợ: type, properties, required, items, enum, description
        """
        if not isinstance(schema, dict):
            return schema

        # Các trường được phép trong schema Gemini
        allowed_fields = {
            "type",
            "properties",
            "required",
            "items",
            "enum",
            "description",
            "default",
            "format",
        }

        sanitized = {}
        for key, value in schema.items():
            if key not in allowed_fields:
                continue

            if key == "properties" and isinstance(value, dict):
                sanitized[key] = {
                    prop_name: LLMProvider._sanitize_schema(prop_schema)
                    for prop_name, prop_schema in value.items()
                }
            elif key == "items" and isinstance(value, dict):
                sanitized[key] = LLMProvider._sanitize_schema(value)
            else:
                sanitized[key] = value

        return sanitized

    @staticmethod
    def _build_tools(funcs: List[Dict[str, Any]] | None):
        if not funcs:
            return None
        return [
            types.Tool(
                function_declarations=[
                    types.FunctionDeclaration(
                        name=f["function"]["name"],
                        description=f["function"]["description"],
                        parameters=LLMProvider._sanitize_schema(
                            f["function"]["parameters"]
                        ),
                    )
                    for f in funcs
                ]
            )
        ]

    # Tài liệu Gemini đề cập, không cần duy trì session-id, trực tiếp ghép dialogue
    def response(self, session_id, dialogue, **kwargs):
        yield from self._generate(dialogue, None)

    def response_with_functions(self, session_id, dialogue, functions=None):
        yield from self._generate(dialogue, self._build_tools(functions))

    def _generate(self, dialogue, tools):
        role_map = {"assistant": "model", "user": "user"}
        contents: list = []
        # Ghép nối đối thoại
        for m in dialogue:
            r = m["role"]

            if r == "assistant" and "tool_calls" in m:
                tc = m["tool_calls"][0]
                contents.append(
                    {
                        "role": "model",
                        "parts": [
                            {
                                "function_call": {
                                    "name": tc["function"]["name"],
                                    "args": json.loads(tc["function"]["arguments"]),
                                }
                            }
                        ],
                    }
                )
                continue

            if r == "tool":
                contents.append(
                    {
                        "role": "user",
                        "parts": [{"text": str(m.get("content", ""))}],
                    }
                )
                continue

            contents.append(
                {
                    "role": role_map.get(r, "user"),
                    "parts": [{"text": str(m.get("content", ""))}],
                }
            )

        stream: GenerateContentResponse = self.model.generate_content(
            contents=contents,
            generation_config=self.gen_cfg,
            tools=tools,
            stream=True,
        )

        try:
            for chunk in stream:
                cand = chunk.candidates[0]
                for part in cand.content.parts:
                    # a) Gọi hàm - thường là đoạn cuối cùng mới là gọi hàm
                    if getattr(part, "function_call", None):
                        fc = part.function_call
                        yield None, [
                            SimpleNamespace(
                                id=uuid.uuid4().hex,
                                type="function",
                                function=SimpleNamespace(
                                    name=fc.name,
                                    arguments=json.dumps(
                                        dict(fc.args), ensure_ascii=False
                                    ),
                                ),
                            )
                        ]
                        return
                    # b) Văn bản thông thường
                    if getattr(part, "text", None):
                        yield part.text if tools is None else (part.text, None)

        finally:
            if tools is not None:
                yield None, None  # chế độ hàm kết thúc, trả về gói trống

    # Đóng stream, dự trữ phương thức chức năng ngắt đối thoại trong tương lai, tài liệu chính thức khuyến nghị đóng stream trước đó để giảm hiệu quả chi phí hạn ngạch và sử dụng tài nguyên
    @staticmethod
    def _safe_finish_stream(stream: GenerateContentResponse):
        if hasattr(stream, "resolve"):
            stream.resolve()  # Gemini SDK version ≥ 0.5.0
        elif hasattr(stream, "close"):
            stream.close()  # Gemini SDK version < 0.5.0
        else:
            for _ in stream:  # Dự phòng tiêu thụ hết
                pass
