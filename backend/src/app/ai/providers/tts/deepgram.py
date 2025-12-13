import asyncio
from typing import Any, Dict, Optional

import requests

try:  # pragma: no cover - phụ thuộc môi trường
    from deepgram import DeepgramClient  # type: ignore
except ImportError:
    DeepgramClient = None  # type: ignore

try:  # pragma: no cover - phụ thuộc môi trường
    from deepgram import SpeakOptions  # type: ignore
except ImportError:
    SpeakOptions = None  # type: ignore

try:  # pragma: no cover - phụ thuộc môi trường
    from deepgram import DeepgramError  # type: ignore
except ImportError:
    DeepgramError = Exception  # type: ignore

from app.ai.providers.tts.base import TTSProviderBase
from app.core.logger import setup_logging
from app.ai.utils.util import check_model_key

TAG = __name__
logger = setup_logging()


class TTSProvider(TTSProviderBase):
    def __init__(self, config: Dict[str, Any], delete_audio_file: bool):
        super().__init__(config, delete_audio_file)

        self.api_key = config.get("api_key")
        model_key_msg = check_model_key("Deepgram TTS", self.api_key or "")
        if model_key_msg:
            logger.bind(tag=TAG).error(model_key_msg)

        if DeepgramClient is None:
            raise ImportError(
                "Không tìm thấy lớp DeepgramClient trong deepgram-sdk. "
                "Vui lòng cài đặt (hoặc nâng cấp) deepgram-sdk >= 3 bằng `pip install --upgrade deepgram-sdk`."
            )

        if not self.api_key:
            raise ValueError("Cần cấu hình `api_key` cho Deepgram TTS.")

        self.model = config.get("model", "aura-asteria-en")
        self.voice = config.get("voice")
        self.encoding = config.get("encoding")
        self.sample_rate = self._parse_int(config.get("sample_rate"))
        self.container = config.get("container")
        self.format = config.get("format", self.container or "mp3")
        self.audio_file_type = self.format

        client_kwargs: Dict[str, Any] = {}
        try:
            self.client = DeepgramClient(self.api_key, **client_kwargs)  # type: ignore
        except TypeError:
            self.client = DeepgramClient(api_key=self.api_key, **client_kwargs)  # type: ignore

        self._options_template = self._build_options_template()

    def _build_options_template(self) -> Dict[str, Any]:
        options: Dict[str, Any] = {"model": self.model}
        if self.voice:
            options["voice"] = self.voice
        if self.encoding:
            options["encoding"] = self.encoding
        if self.sample_rate:
            options["sample_rate"] = self.sample_rate
        if self.container:
            options["container"] = self.container
        return options

    def _create_options(self) -> Any:
        if SpeakOptions:
            try:
                return SpeakOptions(**self._options_template)  # type: ignore
            except TypeError:
                # Nếu phiên bản SDK không hỗ trợ tham số nào đó, quay lại dict
                pass
        return dict(self._options_template)

    @staticmethod
    def _parse_int(value: Optional[Any]) -> Optional[int]:
        if value is None:
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _extract_audio_bytes(response: Any) -> bytes:
        if response is None:
            raise RuntimeError("Deepgram trả về phản hồi rỗng.")

        if isinstance(response, (bytes, bytearray)):
            return bytes(response)

        if hasattr(response, "get_as_bytes"):
            return response.get_as_bytes()

        if hasattr(response, "getvalue"):
            return response.getvalue()

        if hasattr(response, "read"):
            data = response.read()
            if asyncio.iscoroutine(data):
                raise RuntimeError("Deepgram trả về coroutine chưa được await.")
            return data

        raise RuntimeError("Không thể trích xuất dữ liệu âm thanh từ phản hồi Deepgram.")

    async def text_to_speak(self, text: str, output_file: Optional[str]):
        options = self._create_options()

        try:
            response = await asyncio.to_thread(
                self._invoke_speak_sdk,
                text,
                options,
            )
        except AttributeError:
            response = await asyncio.to_thread(
                self._invoke_speak_http,
                text,
            )
        except DeepgramError as err:  # type: ignore
            raise Exception(f"Deepgram TTS yêu cầu thất bại: {err}") from err
        except Exception:
            # Fallback HTTP nếu SDK không tương thích
            response = await asyncio.to_thread(
                self._invoke_speak_http,
                text,
            )

        audio_bytes = self._extract_audio_bytes(response)

        if output_file:
            with open(output_file, "wb") as handle:
                handle.write(audio_bytes)
            return None

        return audio_bytes

    def _invoke_speak_sdk(self, text: str, options: Any) -> Any:
        speak_client = getattr(self.client, "speak", None)
        if speak_client is None:
            raise AttributeError("Deepgram client không có thuộc tính speak.")

        method = getattr(speak_client, "v", None)
        if callable(method):
            try:
                return method(text, options)
            except TypeError:
                return method({"text": text}, options)

        version_client = None
        for version_attr in ("v1", "v2"):
            version_client = getattr(speak_client, version_attr, None)
            if version_client:
                break

        if version_client:
            for candidate_name in ("tts", "text", "speak", "generate"):
                candidate = getattr(version_client, candidate_name, None)
                if callable(candidate):
                    try:
                        return candidate(text, options)
                    except TypeError:
                        return candidate({"text": text}, options)

        raise AttributeError("Không tìm thấy phương thức speak phù hợp trong deepgram-sdk.")

    def _invoke_speak_http(self, text: str) -> bytes:
        params: Dict[str, Any] = {}
        if self.model:
            params["model"] = self.model
        if self.voice:
            params["voice"] = self.voice
        if self.encoding:
            params["encoding"] = self.encoding
        if self.sample_rate:
            params["sample_rate"] = self.sample_rate
        if self.container:
            params["container"] = self.container
        if self.format:
            params["format"] = self.format

        payload = {"text": text}

        headers = {
            "Authorization": f"Token {self.api_key}",
            "Content-Type": "application/json",
        }

        response = requests.post(
            "https://api.deepgram.com/v1/speak",
            params=params or None,
            json=payload,
            headers=headers,
            timeout=60,
        )
        if response.status_code != 200:
            raise Exception(
                f"Deepgram TTS yêu cầu thất bại: {response.status_code} - {response.text}"
            )
        return response.content
