"""
ElevenLabs Speech-to-Text Realtime WebSocket Provider

Tài liệu tham khảo:
https://elevenlabs.io/docs/api-reference/speech-to-text/v-1-speech-to-text-realtime

WebSocket URL: wss://api.elevenlabs.io/v1/speech-to-text/realtime
Authentication: xi-api-key header hoặc ?token= query param

Message types nhận về:
- session_started: Session được thiết lập thành công
- partial_transcript: Transcript tạm thời (realtime UI)
- committed_transcript: Transcript chốt cuối cùng
- committed_transcript_with_timestamps: Transcript với timestamps từng từ
- scribe_*_error: Các loại lỗi khác nhau
"""

import json
import time
import uuid
import base64
import asyncio
import opuslib_next
import websockets
from typing import Optional, List, Dict, Any
from app.core.logger import setup_logging
from app.ai.providers.asr.base import ASRProviderBase
from app.ai.providers.asr.dto.dto import InterfaceType

TAG = __name__
logger = setup_logging()


class ASRProvider(ASRProviderBase):
    """ElevenLabs Speech-to-Text Realtime WebSocket Provider"""

    # WebSocket base URL
    WS_BASE_URL = "wss://api.elevenlabs.io/v1/speech-to-text/realtime"

    # Danh sách error message types
    ERROR_TYPES = {
        "scribe_error": "Lỗi chung khi xử lý STT",
        "scribe_auth_error": "Lỗi xác thực (API key/token không hợp lệ)",
        "scribe_quota_exceeded_error": "Vượt quota/credits",
        "scribe_throttled_error": "Bị throttle do gửi quá nhanh",
        "scribe_unaccepted_terms_error": "Chưa chấp nhận điều khoản dịch vụ",
        "scribe_rate_limited_error": "Bị rate limit",
        "scribe_queue_overflow_error": "Hàng đợi server đầy",
        "scribe_resource_exhausted_error": "Hết tài nguyên",
        "scribe_session_time_limit_exceeded_error": "Phiên vượt quá thời gian tối đa",
        "scribe_input_error": "Input không hợp lệ",
        "scribe_chunk_size_exceeded_error": "Chunk quá lớn",
        "scribe_insufficient_audio_activity_error": "Không đủ hoạt động audio",
        "scribe_transcriber_error": "Lỗi nội bộ transcriber",
    }

    def __init__(self, config: Dict[str, Any], delete_audio_file: bool):
        super().__init__()
        self.interface_type = InterfaceType.STREAM
        self.config = config
        self.text = ""
        self.decoder = opuslib_next.Decoder(16000, 1)
        self.asr_ws: Optional[websockets.WebSocketClientProtocol] = None
        self.forward_task: Optional[asyncio.Task] = None
        self.is_processing = False
        self.server_ready = False
        self.session_id: Optional[str] = None

        # API Configuration
        self.api_key = config.get("api_key")
        if not self.api_key:
            raise ValueError("Cần cấu hình `api_key` cho ElevenLabs ASR")

        # Model Configuration
        self.model_id = config.get("model_id", "scribe_v2_realtime")
        self.language_code = config.get("language_code")  # ISO 639-1 hoặc 639-3
        self.include_timestamps = config.get("include_timestamps", False)

        # Audio Configuration
        # Supported formats: pcm_16000, pcm_22050, pcm_24000, pcm_44100, ulaw_8000
        # Dùng ws_audio_format để tránh conflict với performance tester (gán stt.audio_format = "pcm")
        self.ws_audio_format = config.get("audio_format", "pcm_16000")
        self.sample_rate = self._get_sample_rate_from_format(self.ws_audio_format)

        # VAD Configuration
        # commit_strategy: "manual" hoặc "vad"
        self.commit_strategy = config.get("commit_strategy", "vad")
        self.vad_silence_threshold_secs = config.get("vad_silence_threshold_secs", 1.5)
        self.vad_threshold = config.get("vad_threshold", 0.4)
        # min_speech_duration_ms: Range 50-2000
        self.min_speech_duration_ms = config.get("min_speech_duration_ms", 250)
        # min_silence_duration_ms: Range 50-2000 (không phải 2500!)
        self.min_silence_duration_ms = min(
            config.get("min_silence_duration_ms", 1500), 2000
        )

        # Logging
        self.enable_logging = config.get("enable_logging", True)

        # Output
        self.output_dir = config.get("output_dir", "./audio_output")
        self.delete_audio_file = delete_audio_file

        logger.bind(tag=TAG).info(
            f"ElevenLabs ASR khởi tạo | model: {self.model_id} | "
            f"commit_strategy: {self.commit_strategy} | language: {self.language_code}"
        )
        logger.bind(tag=TAG).debug(
            f"[__init__] ✅ ElevenLabsASR instance created successfully | "
            f"api_key_len={len(self.api_key)} | interface_type={self.interface_type} | "
            f"decoder={type(self.decoder).__name__}"
        )

    def _get_sample_rate_from_format(self, audio_format: str) -> int:
        """Lấy sample rate từ audio format string"""
        format_map = {
            "pcm_16000": 16000,
            "pcm_22050": 22050,
            "pcm_24000": 24000,
            "pcm_44100": 44100,
            "ulaw_8000": 8000,
        }
        return format_map.get(audio_format, 16000)

    def _build_ws_url(self) -> str:
        """Xây dựng WebSocket URL với query parameters"""
        params = [f"model_id={self.model_id}"]

        if self.language_code:
            params.append(f"language_code={self.language_code}")

        if self.include_timestamps:
            params.append("include_timestamps=true")

        params.append(f"audio_format={self.ws_audio_format}")
        params.append(f"commit_strategy={self.commit_strategy}")

        # VAD parameters (chỉ khi dùng commit_strategy=vad)
        if self.commit_strategy == "vad":
            params.append(
                f"vad_silence_threshold_secs={self.vad_silence_threshold_secs}"
            )
            params.append(f"vad_threshold={self.vad_threshold}")
            params.append(f"min_speech_duration_ms={self.min_speech_duration_ms}")
            params.append(f"min_silence_duration_ms={self.min_silence_duration_ms}")

        if not self.enable_logging:
            params.append("enable_logging=false")

        query_string = "&".join(params)
        return f"{self.WS_BASE_URL}?{query_string}"

    async def open_audio_channels(self, conn):
        """Mở kênh âm thanh"""
        await super().open_audio_channels(conn)

    async def receive_audio(self, conn, audio: bytes, audio_have_voice: bool):
        """Nhận và xử lý audio từ client"""
        # Khởi tạo audio cache cho voiceprint
        if not hasattr(conn, "asr_audio_for_voiceprint"):
            conn.asr_audio_for_voiceprint = []

        # Lưu audio data
        if audio:
            conn.asr_audio_for_voiceprint.append(audio)

        conn.asr_audio.append(audio)
        conn.asr_audio = conn.asr_audio[-10:]

        # DEBUG: Log state
        logger.bind(tag=TAG).debug(
            f"receive_audio | audio_have_voice={audio_have_voice} | "
            f"is_processing={self.is_processing} | ws={self.asr_ws is not None} | "
            f"server_ready={self.server_ready}"
        )

        # Chỉ khi có giọng nói và chưa đang xử lý thì mở connection
        if audio_have_voice and not self.is_processing:
            try:
                logger.bind(tag=TAG).debug("Khởi tạo WebSocket connection...")
                await self._start_recognition(conn)
            except Exception as e:
                logger.bind(tag=TAG).error(
                    f"Bắt đầu nhận dạng thất bại: {str(e)}", exc_info=True
                )
                await self._cleanup(conn)
                return

        # Gửi audio chunk nếu đang xử lý và server sẵn sàng
        if self.asr_ws and self.is_processing and self.server_ready:
            try:
                pcm_frame = self.decoder.decode(audio, 960)
                await self._send_audio_chunk(pcm_frame)
            except Exception as e:
                logger.bind(tag=TAG).warning(f"Gửi audio thất bại: {str(e)}")
                await self._cleanup(conn)

    async def _send_audio_chunk(self, pcm_data: bytes, commit: bool = False):
        """Gửi audio chunk tới ElevenLabs WebSocket"""
        if not self.asr_ws:
            logger.bind(tag=TAG).debug("ERROR: asr_ws is None, không thể gửi audio")
            return

        try:
            # Encode audio data thành base64
            audio_base64 = base64.b64encode(pcm_data).decode("utf-8")

            message = {
                "message_type": "input_audio_chunk",
                "audio_base_64": audio_base64,
                "sample_rate": self.sample_rate,
            }

            # Nếu dùng manual commit strategy
            if commit and self.commit_strategy == "manual":
                message["commit"] = True

            logger.bind(tag=TAG).debug(
                f"Gửi audio chunk | size={len(pcm_data)} bytes | "
                f"base64_len={len(audio_base64)} | commit={commit}"
            )
            await self.asr_ws.send(json.dumps(message))
        except Exception as e:
            logger.bind(tag=TAG).error(f"Lỗi gửi audio chunk: {str(e)}", exc_info=True)

    async def _start_recognition(self, conn):
        """Bắt đầu phiên nhận dạng"""
        ws_url = self._build_ws_url()
        headers = {"xi-api-key": self.api_key}

        logger.bind(tag=TAG).debug(
            f"[_start_recognition] Khởi tạo WebSocket connection"
        )
        logger.bind(tag=TAG).debug(f"  - URL: {ws_url[:100]}...")
        logger.bind(tag=TAG).debug(f"  - API Key length: {len(self.api_key)}")
        logger.bind(tag=TAG).debug(
            f"  - Model: {self.model_id} | Strategy: {self.commit_strategy}"
        )

        try:
            # Sử dụng extra_headers (websockets >= 10.0) hoặc thêm vào URL
            # Một số phiên bản dùng additional_headers, một số dùng extra_headers
            self.asr_ws = await websockets.connect(
                ws_url,
                extra_headers=headers,
                max_size=1000000000,
                ping_interval=20,
                ping_timeout=10,
                close_timeout=5,
            )
            logger.bind(tag=TAG).info(
                "✅ WebSocket connection established successfully"
            )
        except Exception as e:
            logger.bind(tag=TAG).error(
                f"❌ WebSocket connection failed: {str(e)}", exc_info=True
            )
            raise

        self.is_processing = True
        self.server_ready = False
        logger.bind(tag=TAG).debug(
            f"[_start_recognition] State updated | is_processing=True | server_ready=False"
        )
        self.forward_task = asyncio.create_task(self._forward_results(conn))
        logger.bind(tag=TAG).debug(
            f"[_start_recognition] Forward task created: {self.forward_task.get_name()}"
        )

    async def _forward_results(self, conn):
        """Nhận và xử lý kết quả từ ElevenLabs WebSocket"""
        logger.bind(tag=TAG).debug(
            "[_forward_results] Bắt đầu receive loop, chờ session_started..."
        )
        try:
            while self.asr_ws and not conn.stop_event.is_set():
                try:
                    response = await asyncio.wait_for(self.asr_ws.recv(), timeout=1.0)
                    result = json.loads(response)

                    message_type = result.get("message_type", "")
                    logger.bind(tag=TAG).debug(
                        f"[_forward_results] Nhận message: {message_type}"
                    )

                    # Xử lý theo message type
                    if message_type == "session_started":
                        await self._handle_session_started(conn, result)

                    elif message_type == "partial_transcript":
                        await self._handle_partial_transcript(result)

                    elif message_type == "committed_transcript":
                        if await self._handle_committed_transcript(conn, result):
                            logger.bind(tag=TAG).debug(
                                "[_forward_results] committed_transcript xử lý xong, break"
                            )
                            break

                    elif message_type == "committed_transcript_with_timestamps":
                        if await self._handle_committed_transcript_with_timestamps(
                            conn, result
                        ):
                            logger.bind(tag=TAG).debug(
                                "[_forward_results] committed_transcript_with_timestamps xử lý xong, break"
                            )
                            break

                    elif message_type.startswith("scribe_") and message_type.endswith(
                        "_error"
                    ):
                        await self._handle_error(message_type, result)
                        logger.bind(tag=TAG).debug(
                            "[_forward_results] Error nhận được, break"
                        )
                        break

                    elif message_type == "invalid_request":
                        # Log chi tiết lỗi invalid_request
                        error_msg = result.get(
                            "message", result.get("error", "No message")
                        )
                        logger.bind(tag=TAG).error(
                            f"[_forward_results] ❌ INVALID_REQUEST: {error_msg}"
                        )
                        logger.bind(tag=TAG).error(
                            f"[_forward_results] Full response: {json.dumps(result, indent=2)}"
                        )
                        break

                    else:
                        logger.bind(tag=TAG).debug(
                            f"[_forward_results] Unknown message type: {message_type}"
                        )
                        # Log full message để debug
                        logger.bind(tag=TAG).debug(
                            f"[_forward_results] Full message: {json.dumps(result)}"
                        )

                except asyncio.TimeoutError:
                    logger.bind(tag=TAG).debug("[_forward_results] Timeout chờ message")
                    continue
                except websockets.exceptions.ConnectionClosed as e:
                    logger.bind(tag=TAG).warning(
                        f"[_forward_results] WebSocket connection closed: {e}"
                    )
                    break
                except Exception as e:
                    logger.bind(tag=TAG).error(
                        f"[_forward_results] Xử lý kết quả thất bại: {str(e)}",
                        exc_info=True,
                    )
                    break

        except Exception as e:
            logger.bind(tag=TAG).error(
                f"[_forward_results] Forward results thất bại: {str(e)}", exc_info=True
            )
        finally:
            logger.bind(tag=TAG).debug("[_forward_results] Kết thúc, gọi cleanup")
            await self._cleanup(conn)

    async def _handle_session_started(self, conn, result: Dict[str, Any]):
        """Xử lý session_started message"""
        self.session_id = result.get("session_id")
        config = result.get("config", {})

        logger.bind(tag=TAG).info(
            f"✅ ElevenLabs session started | session_id: {self.session_id} | "
            f"model: {config.get('model_id')} | language: {config.get('language_code')}"
        )

        logger.bind(tag=TAG).debug(f"[_handle_session_started] Full config: {config}")

        self.server_ready = True
        logger.bind(tag=TAG).debug(
            "[_handle_session_started] server_ready=True, đang gửi audio cache..."
        )

        # Gửi audio đã cache
        if conn.asr_audio:
            logger.bind(tag=TAG).debug(
                f"[_handle_session_started] Gửi {len(conn.asr_audio)} cached audio chunks"
            )
            for idx, cached_audio in enumerate(conn.asr_audio[-10:]):
                try:
                    pcm_frame = self.decoder.decode(cached_audio, 960)
                    await self._send_audio_chunk(pcm_frame)
                    logger.bind(tag=TAG).debug(
                        f"  - Chunk {idx} sent: {len(pcm_frame)} bytes"
                    )
                except Exception as e:
                    logger.bind(tag=TAG).warning(
                        f"Gửi audio cache chunk {idx} thất bại: {e}"
                    )
                    break
        else:
            logger.bind(tag=TAG).debug(
                "[_handle_session_started] Không có cached audio"
            )

    async def _handle_partial_transcript(self, result: Dict[str, Any]):
        """Xử lý partial_transcript message (kết quả tạm thời)"""
        text = result.get("text", "")
        if text:
            self.text = text
            logger.bind(tag=TAG).debug(f"Partial transcript: {text}")

    async def _handle_committed_transcript(self, conn, result: Dict[str, Any]) -> bool:
        """
        Xử lý committed_transcript message (kết quả chốt cuối)
        Returns: True nếu cần kết thúc session
        """
        text = result.get("text", "")
        if text:
            self.text = text
            logger.bind(tag=TAG).info(f"Committed transcript: {text}")

            conn.reset_vad_states()

            # Truyền audio data đã cache
            audio_data = getattr(conn, "asr_audio_for_voiceprint", [])
            await self.handle_voice_stop(conn, audio_data)

            # Clear cache
            conn.asr_audio_for_voiceprint = []
            return True

        return False

    async def _handle_committed_transcript_with_timestamps(
        self, conn, result: Dict[str, Any]
    ) -> bool:
        """
        Xử lý committed_transcript_with_timestamps message
        Returns: True nếu cần kết thúc session
        """
        text = result.get("text", "")
        language_code = result.get("language_code", "")
        words = result.get("words", [])

        if text:
            self.text = text
            logger.bind(tag=TAG).info(
                f"Committed transcript (timestamps): {text} | language: {language_code}"
            )

            # Log word timestamps nếu cần debug
            if words:
                logger.bind(tag=TAG).debug(f"Word count: {len(words)}")

            conn.reset_vad_states()

            audio_data = getattr(conn, "asr_audio_for_voiceprint", [])
            await self.handle_voice_stop(conn, audio_data)

            conn.asr_audio_for_voiceprint = []
            return True

        return False

    async def _handle_error(self, error_type: str, result: Dict[str, Any]):
        """Xử lý các error messages"""
        error_desc = self.ERROR_TYPES.get(error_type, "Unknown error")
        error_detail = result.get("message", result.get("error", "No details"))

        logger.bind(tag=TAG).error(
            f"ElevenLabs STT error | type: {error_type} | "
            f"desc: {error_desc} | detail: {error_detail}"
        )

    async def _cleanup(self, conn):
        """Dọn dẹp tài nguyên"""
        logger.bind(tag=TAG).debug(
            f"[_cleanup] Bắt đầu cleanup ASR session | "
            f"is_processing={self.is_processing} | server_ready={self.server_ready} | "
            f"asr_ws={self.asr_ws is not None} | forward_task={self.forward_task is not None}"
        )

        # Clear audio cache
        if conn and hasattr(conn, "asr_audio_for_voiceprint"):
            cache_len = len(conn.asr_audio_for_voiceprint)
            conn.asr_audio_for_voiceprint = []
            logger.bind(tag=TAG).debug(
                f"[_cleanup] Cleared {cache_len} cached audio chunks"
            )

        # Reset trạng thái
        self.is_processing = False
        self.server_ready = False
        self.session_id = None
        logger.bind(tag=TAG).debug(
            "[_cleanup] State reset: is_processing=False, server_ready=False, session_id=None"
        )

        # Cancel forward task
        if self.forward_task and not self.forward_task.done():
            logger.bind(tag=TAG).debug("[_cleanup] Cancelling forward task...")
            self.forward_task.cancel()
            try:
                await asyncio.wait_for(self.forward_task, timeout=1.0)
            except Exception as e:
                logger.bind(tag=TAG).debug(
                    f"[_cleanup] Forward task cancel: {type(e).__name__}"
                )
            finally:
                self.forward_task = None
                logger.bind(tag=TAG).debug("[_cleanup] Forward task cleaned up")

        # Close WebSocket connection
        if self.asr_ws:
            try:
                logger.bind(tag=TAG).debug(
                    "[_cleanup] Đang đóng WebSocket connection..."
                )
                await asyncio.wait_for(self.asr_ws.close(), timeout=2.0)
                logger.bind(tag=TAG).debug("[_cleanup] ✅ WebSocket connection đã đóng")
            except asyncio.TimeoutError:
                logger.bind(tag=TAG).warning("[_cleanup] WebSocket close timeout")
            except Exception as e:
                logger.bind(tag=TAG).error(f"[_cleanup] Đóng WebSocket lỗi: {e}")
            finally:
                self.asr_ws = None
                logger.bind(tag=TAG).debug("[_cleanup] asr_ws set to None")

        logger.bind(tag=TAG).debug("[_cleanup] ASR session cleanup hoàn tất")

    async def speech_to_text(
        self, opus_data: List[bytes], session_id: str, audio_format: str
    ) -> tuple[str, None]:
        """
                Batch mode: Gửi tất cả audio data qua WebSocket và nhận transcript.
                Dùng cho testing hoặc khi không có realtime s://api.elevenlabs.io/v1/speech-to-text/realtime?model_id=scribe_v2_realtime&l...
        251210 23:12:44[0.1.0_00000000000000][app.ai.providers.asr.elevenlabs_stream]-ERROR-[_transcribe_batch] Error: TypeError: BaseEventLoop.create_connection() got an unexpected keyword argument 'additional_headers'stream.

                Args:
                    opus_data: List of audio bytes (PCM hoặc Opus)
                    session_id: Session ID
                    audio_format: "pcm" hoặc "opus"

                Returns:
                    Tuple (transcript_text, file_path)
        """
        logger.bind(tag=TAG).debug(
            f"[speech_to_text] Batch mode | chunks={len(opus_data)} | format={audio_format}"
        )

        if not opus_data:
            logger.bind(tag=TAG).warning("[speech_to_text] Không có audio data")
            return "", None

        # Decode opus to PCM nếu cần
        if audio_format == "opus":
            pcm_chunks = []
            for chunk in opus_data:
                try:
                    pcm_frame = self.decoder.decode(chunk, 960)
                    pcm_chunks.append(pcm_frame)
                except Exception as e:
                    logger.bind(tag=TAG).warning(f"Decode opus chunk failed: {e}")
            pcm_data = b"".join(pcm_chunks)
        else:
            # PCM format - join directly
            pcm_data = (
                b"".join(opus_data) if isinstance(opus_data[0], bytes) else opus_data[0]
            )

        if not pcm_data:
            logger.bind(tag=TAG).warning("[speech_to_text] PCM data trống sau decode")
            return "", None

        logger.bind(tag=TAG).debug(
            f"[speech_to_text] PCM data size: {len(pcm_data)} bytes"
        )

        # Gửi audio qua WebSocket batch mode
        try:
            transcript = await self._transcribe_batch(pcm_data)
            if transcript:
                logger.bind(tag=TAG).info(f"[speech_to_text] Transcript: {transcript}")
            return transcript or "", None
        except Exception as e:
            logger.bind(tag=TAG).error(
                f"[speech_to_text] Transcribe failed: {e}", exc_info=True
            )
            return "", None

    async def _transcribe_batch(self, pcm_data: bytes) -> Optional[str]:
        """
        Batch transcription: Gửi toàn bộ audio và chờ transcript.

        Args:
            pcm_data: Raw PCM audio data

        Returns:
            Transcript string hoặc None nếu lỗi
        """
        ws_url = self._build_ws_url()
        headers = {"xi-api-key": self.api_key}

        logger.bind(tag=TAG).debug(f"[_transcribe_batch] Connecting to WebSocket...")
        logger.bind(tag=TAG).debug(f"  - URL: {ws_url[:80]}...")

        transcript = ""

        try:
            async with websockets.connect(
                ws_url,
                extra_headers=headers,
                max_size=1000000000,
                ping_interval=20,
                ping_timeout=10,
                close_timeout=5,
            ) as ws:
                logger.bind(tag=TAG).debug("[_transcribe_batch] ✅ WebSocket connected")

                # Task gửi audio
                async def send_audio():
                    # Chờ session_started trước
                    await asyncio.sleep(0.1)

                    # Chia audio thành chunks nhỏ (960 samples = 60ms @ 16kHz)
                    chunk_size = 1920  # 960 samples * 2 bytes
                    total_chunks = (len(pcm_data) + chunk_size - 1) // chunk_size

                    logger.bind(tag=TAG).debug(
                        f"[_transcribe_batch] Sending {total_chunks} chunks..."
                    )

                    for i in range(0, len(pcm_data), chunk_size):
                        chunk = pcm_data[i : i + chunk_size]
                        audio_base64 = base64.b64encode(chunk).decode("utf-8")

                        message = {
                            "message_type": "input_audio_chunk",
                            "audio_base_64": audio_base64,
                            "sample_rate": self.sample_rate,
                        }

                        await ws.send(json.dumps(message))
                        await asyncio.sleep(0.01)  # Không gửi quá nhanh

                    logger.bind(tag=TAG).debug(
                        "[_transcribe_batch] All audio chunks sent"
                    )

                    # Nếu dùng manual commit, gửi commit message
                    if self.commit_strategy == "manual":
                        # Gửi chunk cuối với commit=true
                        commit_msg = {
                            "message_type": "input_audio_chunk",
                            "audio_base_64": "",
                            "sample_rate": self.sample_rate,
                            "commit": True,
                        }
                        await ws.send(json.dumps(commit_msg))
                        logger.bind(tag=TAG).debug(
                            "[_transcribe_batch] Commit message sent"
                        )

                # Task nhận kết quả
                async def receive_results() -> str:
                    nonlocal transcript

                    while True:
                        try:
                            response = await asyncio.wait_for(ws.recv(), timeout=10.0)
                            result = json.loads(response)
                            msg_type = result.get("message_type", "")

                            logger.bind(tag=TAG).debug(
                                f"[_transcribe_batch] Received: {msg_type}"
                            )

                            if msg_type == "session_started":
                                session_id = result.get("session_id")
                                logger.bind(tag=TAG).info(
                                    f"[_transcribe_batch] Session started: {session_id}"
                                )

                            elif msg_type == "partial_transcript":
                                text = result.get("text", "")
                                if text:
                                    transcript = text
                                    logger.bind(tag=TAG).debug(f"  Partial: {text}")

                            elif msg_type == "committed_transcript":
                                text = result.get("text", "")
                                if text:
                                    transcript = text
                                    logger.bind(tag=TAG).info(
                                        f"[_transcribe_batch] ✅ Committed: {text}"
                                    )
                                return transcript

                            elif msg_type == "committed_transcript_with_timestamps":
                                text = result.get("text", "")
                                if text:
                                    transcript = text
                                    logger.bind(tag=TAG).info(
                                        f"[_transcribe_batch] ✅ Committed (timestamps): {text}"
                                    )
                                return transcript

                            elif msg_type.startswith("scribe_") and msg_type.endswith(
                                "_error"
                            ):
                                error_desc = self.ERROR_TYPES.get(msg_type, "Unknown")
                                error_detail = result.get("message", "No details")
                                logger.bind(tag=TAG).error(
                                    f"[_transcribe_batch] ❌ Error: {msg_type} - {error_desc} - {error_detail}"
                                )
                                return ""

                        except asyncio.TimeoutError:
                            logger.bind(tag=TAG).warning(
                                "[_transcribe_batch] Timeout waiting for response"
                            )
                            return transcript  # Trả về partial nếu có

                # Chạy song song gửi và nhận
                send_task = asyncio.create_task(send_audio())
                receive_task = asyncio.create_task(receive_results())

                # Chờ cả hai hoàn thành (với timeout tổng)
                try:
                    await asyncio.wait_for(
                        asyncio.gather(send_task, receive_task), timeout=30.0
                    )
                except asyncio.TimeoutError:
                    logger.bind(tag=TAG).warning("[_transcribe_batch] Total timeout")
                    send_task.cancel()
                    receive_task.cancel()

                return transcript

        except websockets.exceptions.InvalidStatusCode as e:
            logger.bind(tag=TAG).error(
                f"[_transcribe_batch] WebSocket connection failed: HTTP {e.status_code}"
            )
            if e.status_code == 401:
                logger.bind(tag=TAG).error("  → API key không hợp lệ hoặc hết hạn")
            elif e.status_code == 403:
                logger.bind(tag=TAG).error("  → Không có quyền truy cập API")
            return None
        except Exception as e:
            logger.bind(tag=TAG).error(
                f"[_transcribe_batch] Error: {type(e).__name__}: {str(e)}",
                exc_info=True,
            )
            return None

    async def close(self):
        """Đóng tài nguyên"""
        await self._cleanup(None)

        if hasattr(self, "decoder") and self.decoder is not None:
            try:
                del self.decoder
                self.decoder = None
                logger.bind(tag=TAG).debug("ElevenLabs decoder resources released")
            except Exception as e:
                logger.bind(tag=TAG).debug(f"Lỗi khi giải phóng decoder: {e}")
