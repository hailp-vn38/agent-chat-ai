import asyncio
import json
import os
import time
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlencode

import aiohttp
from aiohttp import ClientError, ClientSession, WSMsgType

from app.ai.providers.asr.base import ASRProviderBase
from app.ai.providers.asr.dto.dto import InterfaceType
from app.core.logger import setup_logging
from app.ai.utils.util import check_model_key

TAG = __name__
logger = setup_logging()


class ASRProvider(ASRProviderBase):
    def __init__(self, config: Dict[str, Any], delete_audio_file: bool):
        super().__init__()
        self.interface_type = InterfaceType.NON_STREAM

        self.api_key = config.get("api_key")
        model_key_msg = check_model_key("Deepgram ASR", self.api_key or "")
        if model_key_msg:
            logger.bind(tag=TAG).error(model_key_msg)

        if not self.api_key:
            raise ValueError("Cần cấu hình `api_key` cho Deepgram ASR.")

        self.delete_audio_file = delete_audio_file

        self.model = config.get("model", "nova-2")
        self.language = config.get("language")
        self.smart_format = self._parse_bool(config.get("smart_format", True))
        self.diarize = self._parse_bool(config.get("diarize"))
        self.numerals = self._parse_bool(config.get("numerals"))
        self.tier = config.get("tier")
        self.version = config.get("version")
        self.callback = config.get("callback")
        self.output_dir = config.get("output_dir", "tmp/")
        os.makedirs(self.output_dir, exist_ok=True)

        self.sample_rate = self._safe_int(config.get("sample_rate"), 16000)
        self.channels = self._safe_int(config.get("channels"), 1)
        self.ws_chunk_size = max(self._safe_int(config.get("ws_chunk_size"), 4096), 1)
        self.stream_timeout = self._safe_float(config.get("ws_timeout"), 15.0)

        self._options_template = self._build_options_template()
        self._http_params = self._build_http_params()
        self._ws_url = self._build_ws_url()

    def _build_options_template(self) -> Dict[str, Any]:
        options: Dict[str, Any] = {"model": self.model}
        if self.language:
            options["language"] = self.language
        if self.smart_format is not None:
            options["smart_format"] = self.smart_format
        if self.diarize is not None:
            options["diarize"] = self.diarize
        if self.numerals is not None:
            options["numerals"] = self.numerals
        if self.tier:
            options["tier"] = self.tier
        if self.version:
            options["version"] = self.version
        if self.callback:
            options["callback"] = self.callback
        return options

    def _build_http_params(self) -> Dict[str, Any]:
        return {
            key: self._stringify_param(value)
            for key, value in self._options_template.items()
            if value is not None
        }

    def _build_ws_url(self) -> str:
        params = dict(self._http_params)
        params.setdefault("encoding", "linear16")
        params.setdefault("sample_rate", str(self.sample_rate))
        params.setdefault("channels", str(self.channels))
        query = urlencode(params)
        return f"wss://api.deepgram.com/v1/listen{('?' + query) if query else ''}"

    @staticmethod
    def _safe_int(value: Any, default: int) -> int:
        try:
            if value is None:
                return default
            if isinstance(value, bool):
                return int(value)
            if isinstance(value, (int, float)):
                return int(value)
            value_str = str(value).strip()
            if not value_str:
                return default
            return int(value_str)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _safe_float(value: Any, default: float) -> float:
        try:
            if value is None:
                return default
            if isinstance(value, bool):
                return float(int(value))
            if isinstance(value, (int, float)):
                return float(value)
            value_str = str(value).strip()
            if not value_str:
                return default
            return float(value_str)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _parse_bool(value: Any) -> Optional[bool]:
        if value is None:
            return None
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            lowered = value.strip().lower()
            if lowered in {"true", "1", "yes", "y"}:
                return True
            if lowered in {"false", "0", "no", "n"}:
                return False
        if isinstance(value, (int, float)):
            return bool(value)
        return None

    async def speech_to_text(
        self, opus_data: List[bytes], session_id: str, audio_format: str = "opus"
    ) -> Tuple[Optional[str], Optional[str]]:
        file_path: Optional[str] = None

        try:
            if audio_format == "pcm":
                pcm_data = opus_data
            else:
                pcm_data = self.decode_opus(opus_data)

            if not pcm_data:
                raise ValueError("Không có dữ liệu âm thanh hợp lệ để nhận dạng.")

            buffer_prep_start = time.time()
            combined_pcm = b"".join(pcm_data)
            total_size = len(combined_pcm)
            if total_size == 0:
                raise ValueError("Không có dữ liệu PCM sau khi ghép nối.")
            logger.bind(tag=TAG).debug(
                f"Chuẩn bị buffer audio mất {time.time() - buffer_prep_start:.3f}s | Kích thước: {total_size} bytes"
            )

            if not self.delete_audio_file:
                persist_start = time.time()
                file_path = self.save_audio_to_file(pcm_data, session_id)
                logger.bind(tag=TAG).debug(
                    f"Lưu audio phục vụ debug mất {time.time() - persist_start:.3f}s | Đường dẫn: {file_path}"
                )

            ws_start = time.time()
            transcript = await self._transcribe_via_websocket(combined_pcm)
            logger.bind(tag=TAG).debug(
                f"Nhận diện giọng nói (WebSocket) mất {time.time() - ws_start:.3f}s"
            )

            if transcript:
                logger.bind(tag=TAG).info(f"Deepgram ASR kết quả: {transcript}")
            else:
                logger.bind(tag=TAG).warning("Deepgram ASR không trả về transcript.")
            return transcript, file_path

        except Exception as err:
            logger.bind(tag=TAG).error(f"Nhận dạng giọng nói thất bại: {err}")
            return "", None
        finally:
            if (
                self.delete_audio_file
                and file_path
                and os.path.exists(file_path)
            ):
                try:
                    os.remove(file_path)
                    logger.bind(tag=TAG).debug(f"Đã xóa file âm thanh tạm: {file_path}")
                except Exception as cleanup_err:
                    logger.bind(tag=TAG).warning(
                        f"Không thể xóa file âm thanh tạm {file_path}: {cleanup_err}"
                    )

    async def _transcribe_via_websocket(self, pcm_bytes: bytes) -> Optional[str]:
        if not pcm_bytes:
            return None

        headers = {"Authorization": f"Token {self.api_key}"}
        timeout = aiohttp.ClientTimeout(total=max(self.stream_timeout, 5.0) + 20.0)
        transcript_holder = {"text": ""}

        async with ClientSession(timeout=timeout) as session:
            try:
                async with session.ws_connect(self._ws_url, headers=headers) as ws:
                    async def send_audio_stream():
                        chunk_size = self.ws_chunk_size
                        view = memoryview(pcm_bytes)
                        for idx in range(0, len(view), chunk_size):
                            await ws.send_bytes(view[idx : idx + chunk_size])
                        await ws.send_str(json.dumps({"type": "CloseStream"}))

                    async def receive_transcripts() -> Optional[str]:
                        final_text = ""
                        async for msg in ws:
                            if msg.type == WSMsgType.TEXT:
                                try:
                                    payload = json.loads(msg.data)
                                except json.JSONDecodeError:
                                    continue

                                if payload.get("type") == "Results":
                                    text = self._extract_transcript(payload)
                                    if text:
                                        final_text = text.strip()
                                        transcript_holder["text"] = final_text
                                    channel = payload.get("channel", {}) or {}
                                    is_final = channel.get("is_final") or payload.get("is_final")
                                    if is_final and final_text:
                                        return final_text
                            elif msg.type == WSMsgType.ERROR:
                                raise ws.exception() or RuntimeError("Deepgram WebSocket báo lỗi.")
                            elif msg.type in (WSMsgType.CLOSE, WSMsgType.CLOSED):
                                break
                        return final_text or transcript_holder.get("text")

                    try:
                        _, transcript_result = await asyncio.wait_for(
                            asyncio.gather(send_audio_stream(), receive_transcripts()),
                            timeout=max(self.stream_timeout, 5.0) + 25.0,
                        )
                    except asyncio.TimeoutError as timeout_err:
                        await ws.close()
                        raise RuntimeError("Quá thời gian chờ phản hồi từ Deepgram WebSocket.") from timeout_err

                    if not ws.closed:
                        await ws.close()

                    if transcript_result:
                        return transcript_result
                    if transcript_holder["text"]:
                        return transcript_holder["text"]
                    return None
            except ClientError as conn_err:
                raise RuntimeError(f"Kết nối WebSocket Deepgram thất bại: {conn_err}") from conn_err

    @staticmethod
    def _dict_from_response(response: Any) -> Dict[str, Any]:
        if response is None:
            return {}

        if isinstance(response, dict):
            return response

        if hasattr(response, "to_dict"):
            try:
                return response.to_dict()  # type: ignore
            except Exception:
                pass

        if hasattr(response, "json") and callable(response.json):
            try:
                return response.json()  # type: ignore
            except Exception:
                pass

        if isinstance(response, str):
            try:
                return json.loads(response)
            except json.JSONDecodeError:
                return {}

        try:
            return dict(response)  # type: ignore
        except Exception:
            return getattr(response, "__dict__", {}) or {}

    @classmethod
    def _extract_transcript(cls, response: Any) -> str:
        data = cls._dict_from_response(response)
        if not data:
            return ""

        # Deepgram có thể trả về trong trường "results" -> "channels" -> "alternatives"
        results = data.get("results") or {}
        if isinstance(results, list):
            channels = results
        else:
            channels = results.get("channels") if isinstance(results, dict) else None

        if channels:
            first_channel = channels[0] if isinstance(channels, list) else channels
            if isinstance(first_channel, dict):
                alternatives = first_channel.get("alternatives")
                if alternatives:
                    first_alt = alternatives[0] if isinstance(alternatives, list) else alternatives
                    if isinstance(first_alt, dict):
                        transcript = first_alt.get("transcript")
                        if transcript:
                            return transcript.strip()
                        paragraphs = first_alt.get("paragraphs")
                        if isinstance(paragraphs, dict):
                            paragraphs_list = paragraphs.get("paragraphs")
                            if isinstance(paragraphs_list, list) and paragraphs_list:
                                joined = " ".join(
                                    [
                                        p.get("text", "").strip()
                                        for p in paragraphs_list
                                        if isinstance(p, dict)
                                    ]
                                ).strip()
                                if joined:
                                    return joined

        # Fallback: nếu response có trường "channel" (SDK cũ)
        channel = data.get("channel")
        if isinstance(channel, dict):
            alternatives = channel.get("alternatives")
            if isinstance(alternatives, list) and alternatives:
                transcript = alternatives[0].get("transcript")
                if transcript:
                    return transcript.strip()

        return ""

    @staticmethod
    def _stringify_param(value: Any) -> Any:
        if isinstance(value, bool):
            return str(value).lower()
        return value
