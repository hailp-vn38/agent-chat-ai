"""
Quản lý 1 WebSocket connection từ device ESP32

Adapted cho FastAPI + ThreadPool architecture
"""

from __future__ import annotations

import os
import sys
import copy
import json
import uuid
import time
import queue
import asyncio
import threading
import traceback
import subprocess
from typing import Dict, Any, Optional, Union
from collections import deque
from starlette.websockets import WebSocket, WebSocketState, WebSocketDisconnect
from app.ai.utils import textUtils
from app.ai.utils.prompt_manager import PromptManager
from app.ai.utils.util import extract_json_from_string
from app.ai.handle.reportHandle import report
from app.ai.handle.textHandle import handleTextMessage
from app.ai.providers.tools.unified_tool_handler import UnifiedToolHandler
from app.ai.providers.tts.dto.dto import ContentType, SentenceType, TTSMessageDTO
from app.ai.utils.dialogue import Dialogue, Message
from app.ai.utils.cache import async_cache_manager, CacheType
from app.core.auth import AuthenticationError
from app.core.db.database import local_session

from app.core.logger import (
    build_module_string,
    create_connection_logger,
    setup_logging,
)
from app.ai.module_factory import (
    load_modules_from_agent,
    load_modules_from_providers,
)
from app.ai.initializers.component_initializer import (
    initialize_memory_component,
    initialize_intent_component,
    initialize_voiceprint_component,
    initialize_asr_component,
    initialize_tts_component,
)
from app.ai.utils.agent_module_loader import (
    apply_agent_modules,
    apply_agent_config_fields,
)
from app.ai.plugins_func.register import ActionResponse
from app.ai.providers.tts.base import TTSProviderBase
from app.ai.providers.llm.base import LLMProviderBase
from app.ai.providers.asr.base import ASRProviderBase
from app.ai.providers.intent.base import IntentProviderBase
from app.ai.providers.memory.base import MemoryProviderBase
from app.ai.providers.vad.base import VADProviderBase
from app.ai.providers.voiceprints.voiceprint_provider import VoiceprintProvider
from app.services.agent_service import AgentService


try:
    from app.ai.plugins_func.loadplugins import auto_import_modules
except ModuleNotFoundError:

    def auto_import_modules(*_args, **_kwargs):
        return None


TAG = __name__

auto_import_modules("app.ai.plugins_func.functions")
_startup_logger = setup_logging()
try:
    from app.ai.plugins_func.register import all_function_registry

    _startup_logger.bind(tag=TAG).info(
        f"Các plugin đã nạp: {list(all_function_registry.keys())}"
    )
except Exception as plugin_import_error:
    _startup_logger.bind(tag=TAG).warning(
        f"Không thể liệt kê plugin đã nạp: {plugin_import_error}"
    )


class TTSException(RuntimeError):
    pass


class DeviceNotFoundException(Exception):
    pass


class ConnectionHandler:
    def __init__(
        self,
        config: Dict[str, Any],
        _vad,
        _asr,
        _llm,
        _memory,
        _intent,
        thread_pool=None,  # NEW: ThreadPoolService từ app.state
        server=None,
        agent=None,  # NEW: Agent info từ auth state
        agent_service=None,  # NEW: Agent service dependency
    ):
        self.common_config = config
        self.config = copy.deepcopy(config)
        self.session_id = str(uuid.uuid4())
        self.logger = setup_logging()
        self.server = server  # Giữ tham chiếu tới instance server
        self.thread_pool = thread_pool  # NEW: global thread pool
        self.agent = agent or {}
        self.agent_service: AgentService = (
            agent_service  # NEW: Agent service dependency
        )
        self.read_config_from_api = self.config.get("read_config_from_api", False)

        self.websocket = None
        self.headers = None
        self.device_id = None
        self.device_mac_address = None  # NEW: MAC address từ device_info
        self.client_ip = None
        self.prompt = None
        self.welcome_msg = None
        self.max_output_size = 0
        self.chat_history_conf = 0
        self.audio_format = "opus"
        self.gateway_frame_duration = int(
            self.config.get("gateway_frame_duration_ms", 60)
        )
        self._gateway_audio_timestamp = 0

        # Trạng thái phía client
        self.client_abort = False
        self.client_is_speaking = False
        self.client_listen_mode = "auto"

        # Thiết lập luồng và nhiệm vụ bất đồng bộ
        try:
            self.loop = asyncio.get_event_loop()
        except RuntimeError:
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)

        # Đồng bộ trạng thái khởi tạo các thành phần (ASR/VAD/TTS) trước khi nhận audio
        self.components_ready = asyncio.Event()

        self.stop_event = threading.Event()
        # REMOVED: executor không còn cần thiết, dùng submit_blocking_task() thay thế

        # Thread pool cho tác vụ báo cáo
        self.report_queue = queue.Queue()
        self.report_thread = None
        self.report_asr_enable = self.read_config_from_api
        self.report_tts_enable = self.read_config_from_api

        # Các thành phần phụ thuộc
        self.vad: VADProviderBase = None
        self.asr: ASRProviderBase = None
        self.tts: TTSProviderBase = None
        self._asr: ASRProviderBase = _asr
        self._vad: VADProviderBase = _vad
        self.llm: LLMProviderBase = _llm
        self.memory: MemoryProviderBase = _memory
        self.intent: IntentProviderBase = _intent

        # Quản lý nhận diện giọng nói (voiceprint) riêng cho từng kết nối
        self.voiceprint_provider: VoiceprintProvider = None

        # Biến liên quan tới VAD
        self.client_audio_buffer = bytearray()
        self.client_have_voice = False
        self.last_activity_time = 0.0  # Dấu thời gian hoạt động chung (ms)
        self.client_voice_stop = False
        self.client_voice_window = deque(maxlen=5)
        self.last_is_voice = False

        # Biến liên quan tới ASR
        self.asr_audio = []
        self.asr_audio_queue = queue.Queue()

        # Biến liên quan tới LLM
        self.llm_finish_task = True
        self.dialogue = Dialogue()

        # Biến liên quan tới TTS
        self.sentence_id = None
        self.tts_MessageText = ""

        # Biến liên quan tới IoT
        self.iot_descriptors = {}
        self.func_handler = None

        self.cmd_exit = self.config.get("exit_commands", [])

        # Điều khiển đóng kết nối sau khi kết thúc trò chuyện
        self.close_after_chat = False
        self.load_function_plugin = False
        self.intent_type = "nointent"
        self._closing = False

        self.timeout_seconds = (
            int(self.config.get("close_connection_no_voice_time", 120)) + 60
        )
        self.timeout_task = None

        # {"mcp":true} nghĩa là bật tính năng MCP
        self.features = None

        # Đánh dấu kết nối đến từ MQTT
        self.conn_from_mqtt_gateway = False

        # FFmpeg streamer cho URL music streaming
        self.current_streamer = None

        # Khởi tạo agent_id, device_id và device_mac_address từ agent info
        self.agent_id = self.agent.get("id")  # Agent UUID
        if self.agent.get("device"):
            self.device_id = self.agent.get("device").get("id")
            self.device_mac_address = self.agent.get("device").get("mac_address")

        # Load chat_history_conf từ agent (0=disabled, 1=text, 2=text+audio)
        if self.agent.get("chat_history_conf") is not None:
            self.chat_history_conf = int(self.agent.get("chat_history_conf"))

        # Khởi tạo bộ quản lý prompt
        self.prompt_manager = PromptManager(config, self.logger)

    def get_device_id_for_json(self) -> str:
        """Return device UUID as string for JSON serialization"""
        if self.device_id:
            return str(self.device_id)
        return ""

    def get_device_mac_for_mqtt(self) -> str:
        """Return device MAC address string for MQTT topics"""
        return self.device_mac_address or ""

    def submit_blocking_task(self, func, *args, **kwargs):
        """
        Submit blocking task vào thread pool hoặc fallback asyncio.to_thread

        Ưu tiên dùng thread_pool nếu có, fallback sang asyncio.to_thread

        Args:
            func: Sync function cần chạy trong thread riêng
            *args, **kwargs: Tham số của function
        """
        if self.thread_pool:
            # Có thread_pool: dùng run_blocking
            asyncio.create_task(self.thread_pool.run_blocking(func, *args, **kwargs))
        else:
            # Fallback: dùng asyncio.to_thread (Python 3.9+)
            asyncio.create_task(asyncio.to_thread(func, *args, **kwargs))

    async def handle_connection(
        self, websocket: WebSocket, headers_override: Optional[Dict[str, str]] = None
    ):
        try:
            await self._prepare_connection(websocket)
            await self._receive_loop()
        except AuthenticationError as e:
            self.logger.bind(tag=TAG).error(f"Authentication failed: {str(e)}")
            return
        except Exception as e:
            stack_trace = traceback.format_exc()
            self.logger.bind(tag=TAG).error(f"Connection error: {str(e)}-{stack_trace}")
            return
        finally:
            try:
                await self._save_and_close(websocket)
            except Exception as final_error:
                self.logger.bind(tag=TAG).error(
                    f"Lỗi trong bước dọn dẹp cuối: {final_error}"
                )
                try:
                    await self.close(websocket)
                except Exception as close_error:
                    self.logger.bind(tag=TAG).error(
                        f"Lỗi khi cưỡng bức đóng kết nối: {close_error}"
                    )

    async def _prepare_connection(self, websocket: WebSocket):
        """Thiết lập trạng thái ban đầu cho một kết nối mới."""
        self._assign_websocket(websocket)
        self._extract_headers(websocket)
        self._ensure_device_identity()
        self._detect_mqtt_gateway(websocket)
        self._initialize_activity_tracking()
        self._start_timeout_monitor()
        self._prepare_welcome_message()
        await self._mark_device_connected()
        asyncio.create_task(self._init_sequence())

    async def _init_sequence(self):
        """Chạy agent config load -> components init theo sequence (NON-BLOCKING overall)

        Phase 1: Load private config từ API (nếu cần)
        Phase 2: Init components (ASR/VAD/TTS)
        """
        # Phase 1: Load agent config (may have I/O)
        if self.thread_pool:
            await self.thread_pool.run_blocking(self._initialize_agent_module)
        else:
            await asyncio.to_thread(self._initialize_agent_module)

        # Phase 2: Init components sau khi agent config ready
        self._launch_component_initialization()

    def _assign_websocket(self, websocket: WebSocket):
        self.websocket = websocket

    def _extract_headers(self, websocket: WebSocket):
        """Đọc headers từ websocket và xác định địa chỉ IP của client."""
        # Headers đã được merge trong middleware, lấy từ app state nếu cần
        self.headers = {k: v for k, v in websocket.headers.items()}

        real_ip = self.headers.get("x-real-ip") or self.headers.get("x-forwarded-for")
        if real_ip:
            self.client_ip = real_ip.split(",")[0].strip()
        elif websocket.client:
            self.client_ip = websocket.client[0]
        else:
            self.client_ip = "unknown"

        self.logger.bind(tag=TAG).debug(
            f"{self.client_ip} conn - Headers: {self.headers}"
        )

    def _ensure_device_identity(self):
        """Đảm bảo giá trị device_id được thiết lập từ device_info."""
        # device_id đã được set từ device_info trong __init__
        # nếu không có thì thử từ headers (fallback)
        if not self.device_id:
            self.device_id = self.headers.get("device-id")

    def _detect_mqtt_gateway(self, websocket: WebSocket):
        """Xác định kết nối có đến từ MQTT gateway hay không."""
        request_path = websocket.url.path
        if websocket.url.query:
            request_path += f"?{websocket.url.query}"
        self.conn_from_mqtt_gateway = request_path.endswith("?from=mqtt_gateway")
        if self.conn_from_mqtt_gateway:
            self.logger.bind(tag=TAG).info("Kết nối đến từ MQTT Gateway")

    def _initialize_activity_tracking(self):
        """Thiết lập dấu thời gian hoạt động ban đầu."""
        self.last_activity_time = time.time() * 1000

    def _start_timeout_monitor(self):
        """Khởi chạy nhiệm vụ theo dõi timeout nếu chưa chạy."""
        if self.timeout_task and not self.timeout_task.done():
            return
        self.timeout_task = asyncio.create_task(self._check_timeout())

    def _prepare_welcome_message(self):
        """Sao chép thông điệp chào mừng cho phiên mới."""
        self.welcome_msg = copy.deepcopy(self.config.get("message_welcome", {}))
        if not isinstance(self.welcome_msg, dict):
            self.welcome_msg = {}
        self.welcome_msg["session_id"] = self.session_id

    async def _mark_device_connected(self):
        """Mark device as connected using DeviceStatusManager for atomic DB+cache sync."""
        if not self.device_id:
            self.logger.debug("No device_id available, skipping device connected mark")
            return

        try:
            # Use DeviceStatusManager for atomic DB+cache operations
            if self.agent_service and self.device_id:
                async with local_session() as db:
                    try:
                        result = await self.agent_service.device_status.mark_connected(
                            db=db,
                            device_id=self.device_id,
                            ttl=300,
                        )
                        if result:
                            self.logger.bind(tag=TAG).debug(
                                f"✅ Device {self.device_id} marked as CONNECTED (DB + cache)"
                            )
                        else:
                            self.logger.bind(tag=TAG).debug(
                                f"⚠️ Device {self.device_id} marked in cache (device not in DB yet)"
                            )
                    except Exception as e:
                        self.logger.bind(tag=TAG).error(
                            f"Failed to mark device {self.device_id} as CONNECTED: {e}"
                        )
            else:
                # Fallback: cache only (legacy support)
                await async_cache_manager.set(
                    cache_type=CacheType.DEVICE,
                    key=f"{self.device_id}:status",
                    value="connected",
                    ttl=300,
                )
                self.logger.bind(tag=TAG).debug(
                    f"✅ Device {self.device_id} tracked as CONNECTED (cache only)"
                )
        except Exception as e:
            self.logger.bind(tag=TAG).error(f"Failed to mark device connected: {e}")

    def _launch_component_initialization(self):
        """Khởi tạo các mô-đun VAD/ASR/TTS trên thread riêng."""
        if self.thread_pool:
            asyncio.create_task(
                self.thread_pool.run_blocking(self._initialize_components)
            )
        else:
            # Fallback: dùng asyncio.to_thread nếu không có thread_pool
            asyncio.create_task(asyncio.to_thread(self._initialize_components))

    async def _receive_loop(self):
        """Vòng lặp nhận dữ liệu chính từ WebSocket."""
        if not self.websocket:
            return

        try:
            while True:
                incoming = await self.websocket.receive()
                msg_type = incoming.get("type")
                if msg_type == "websocket.disconnect":
                    self.logger.bind(tag=TAG).info("Client đã ngắt kết nối")
                    break
                if msg_type != "websocket.receive":
                    continue
                if incoming.get("text") is not None:
                    await self._route_message(incoming["text"])
                elif incoming.get("bytes") is not None:
                    await self._route_message(incoming["bytes"])
        except Exception as e:
            stack_trace = traceback.format_exc()
            self.logger.bind(tag=TAG).error(
                f"Lỗi khi xử lý kết nối: {str(e)}-{stack_trace}"
            )

    async def _save_and_close(self, ws):
        """Lưu trí nhớ rồi đóng kết nối"""
        try:
            # Mark device as disconnected using DeviceStatusManager
            await self._mark_device_disconnected()

            if self.memory:

                def save_memory_task():
                    try:
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        loop.run_until_complete(
                            self.memory.save_memory(self.dialogue.dialogue)
                        )
                    except Exception as e:
                        self.logger.bind(tag=TAG).error(f"Lưu trí nhớ thất bại: {e}")
                    finally:
                        try:
                            loop.close()
                        except Exception:
                            pass

                threading.Thread(target=save_memory_task, daemon=True).start()
        except Exception as e:
            self.logger.bind(tag=TAG).error(f"Lưu trí nhớ thất bại: {e}")
        finally:
            try:
                await self.close(ws)
            except Exception as close_error:
                self.logger.bind(tag=TAG).error(
                    f"Lỗi khi đóng kết nối sau khi lưu trí nhớ: {close_error}"
                )

    async def _mark_device_disconnected(self):
        """Mark device as disconnected and clean up cache using DeviceStatusManager."""
        if not self.device_id:
            return

        try:
            # Use DeviceStatusManager for cache cleanup
            if self.agent_service and self.device_id:
                async with local_session() as db:
                    try:
                        await self.agent_service.device_status.mark_disconnected(
                            db=db,
                            device_id=self.device_id,
                        )
                        self.logger.bind(tag=TAG).debug(
                            f"❌ Device {self.device_id} marked as DISCONNECTED"
                        )
                    except Exception as e:
                        self.logger.bind(tag=TAG).error(
                            f"Failed to mark device {self.device_id} as DISCONNECTED: {e}"
                        )
            else:
                # Fallback: direct cache delete (legacy support)
                await async_cache_manager.delete(
                    cache_type=CacheType.CONFIG, key=f"device:{self.device_id}:status"
                )
                self.logger.bind(tag=TAG).info(
                    f"❌ Device {self.device_id} tracked as DISCONNECTED (cache only)"
                )
        except Exception as e:
            self.logger.bind(tag=TAG).error(f"Failed to mark device disconnected: {e}")

    async def _route_message(self, message):
        """Định tuyến thông điệp"""

        if isinstance(message, str):
            await handleTextMessage(self, message)
        elif isinstance(message, bytes):
            if self.vad is None or self.asr is None:
                self.logger.bind(tag=TAG).warning(
                    "Bỏ qua gói âm thanh vì ASR/VAD chưa khởi tạo thành công"
                )
                return

            # Xử lý gói âm thanh đến từ MQTT gateway
            if self.conn_from_mqtt_gateway and len(message) >= 4:
                handled = await self._process_mqtt_audio_message(message)
                if handled:
                    return

            # Không cần thêm header hoặc không có header: đẩy thẳng vào hàng đợi
            self.asr_audio_queue.put(message)

    async def _process_mqtt_audio_message(self, message):
        """
        Xử lý gói âm thanh từ MQTT gateway, hỗ trợ Binary Protocol V2 (legacy) và V3.
        """
        try:
            # Ưu tiên nhận diện V2 để tương thích ngược
            if len(message) >= 16:
                version = int.from_bytes(message[0:2], "big")
                frame_type = int.from_bytes(message[2:4], "big")
                if version == 2 and frame_type in (0, 1):
                    timestamp = int.from_bytes(message[8:12], "big")
                    payload_length = int.from_bytes(message[12:16], "big")
                    if payload_length > len(message) - 16:
                        self.logger.bind(tag=TAG).warning(
                            f"Gói V2 thiếu payload: cần {payload_length}, nhận {len(message) - 16}"
                        )
                        return False
                    payload = message[16 : 16 + payload_length]

                    if frame_type == 0:
                        self._process_websocket_audio(payload, timestamp)
                    elif frame_type == 1:
                        try:
                            await handleTextMessage(self, payload.decode("utf-8"))
                        except UnicodeDecodeError as e:
                            self.logger.bind(tag=TAG).warning(
                                f"Không thể giải mã JSON trong Binary V2: {e}"
                            )
                    return True

            # V3: header 4 byte
            if len(message) >= 4:
                frame_type = message[0]
                payload_length = int.from_bytes(message[2:4], "big")
                if payload_length > len(message) - 4:
                    self.logger.bind(tag=TAG).warning(
                        f"Gói V3 thiếu payload: cần {payload_length}, nhận {len(message) - 4}"
                    )
                    return False
                payload = message[4 : 4 + payload_length]
                if frame_type == 0:
                    timestamp = self._next_gateway_audio_timestamp()
                    self._process_websocket_audio(payload, timestamp)
                    return True
                elif frame_type == 1:
                    try:
                        json_payload = payload.decode("utf-8")
                        await handleTextMessage(self, json_payload)
                        return True
                    except UnicodeDecodeError as e:
                        self.logger.bind(tag=TAG).warning(
                            f"Không thể giải mã JSON trong Binary V3: {e}"
                        )
        except Exception as e:
            self.logger.bind(tag=TAG).error(
                f"Không thể phân tích gói âm thanh WebSocket: {e}"
            )

        return False

    def _next_gateway_audio_timestamp(self):
        frame_duration = max(1, int(getattr(self, "gateway_frame_duration", 60)))
        current_ts = self._gateway_audio_timestamp
        next_ts = (current_ts + frame_duration) % (2**32)
        self._gateway_audio_timestamp = next_ts
        return current_ts

    def _process_websocket_audio(self, audio_data, timestamp):
        """Xử lý gói âm thanh định dạng WebSocket"""
        if not hasattr(self, "audio_timestamp_buffer"):
            self.audio_timestamp_buffer = {}
            self.last_processed_timestamp = 0
            self.max_timestamp_buffer_size = 20

        if timestamp >= self.last_processed_timestamp:
            self.asr_audio_queue.put(audio_data)
            self.last_processed_timestamp = timestamp

            processed_any = True
            while processed_any:
                processed_any = False
                for ts in sorted(self.audio_timestamp_buffer.keys()):
                    if ts > self.last_processed_timestamp:
                        buffered_audio = self.audio_timestamp_buffer.pop(ts)
                        self.asr_audio_queue.put(buffered_audio)
                        self.last_processed_timestamp = ts
                        processed_any = True
                        break
        else:
            if len(self.audio_timestamp_buffer) < self.max_timestamp_buffer_size:
                self.audio_timestamp_buffer[timestamp] = audio_data
            else:
                self.asr_audio_queue.put(audio_data)

    async def handle_restart(self, message):
        """Xử lý yêu cầu khởi động lại server"""
        try:
            self.logger.bind(tag=TAG).info(
                "Nhận yêu cầu khởi động lại server, chuẩn bị thực thi…"
            )

            await self.websocket.send_text(
                json.dumps(
                    {
                        "type": "server",
                        "status": "success",
                        "message": "Server đang khởi động lại...",
                        "content": {"action": "restart"},
                    },
                    ensure_ascii=False,
                )
            )

            def restart_server():
                time.sleep(1)
                self.logger.bind(tag=TAG).info("Đang khởi động lại server…")
                subprocess.Popen(
                    [sys.executable, "app.py"],
                    stdin=sys.stdin,
                    stdout=sys.stdout,
                    stderr=sys.stderr,
                    start_new_session=True,
                )
                os._exit(0)

            threading.Thread(target=restart_server, daemon=True).start()

        except Exception as e:
            self.logger.bind(tag=TAG).error(f"Khởi động lại thất bại: {str(e)}")
            await self.websocket.send_text(
                json.dumps(
                    {
                        "type": "server",
                        "status": "error",
                        "message": f"Restart failed: {str(e)}",
                        "content": {"action": "restart"},
                    },
                    ensure_ascii=False,
                )
            )

    def _initialize_components(self):
        """
        Khởi tạo pipeline âm thanh (VAD/ASR/TTS) và các mô-đun liên quan.
        Chạy trong thread riêng để tránh block event loop chính.
        """

        start_ts = time.perf_counter()
        try:
            self.selected_module_str = build_module_string(
                self.config.get("selected_module", {})
            )
            self.logger = create_connection_logger(self.selected_module_str)

            if self.vad is None:
                self.vad = self._vad

            if self.asr is None:
                self.logger.bind(tag=TAG).debug("Đang khởi tạo mô-đun ASR")
                self._initialize_asr()
            else:
                self.logger.bind(tag=TAG).debug("ASR tái sử dụng từ cache")

            # Khởi tạo nhận diện giọng nói
            self._initialize_voiceprint()

            if self.asr is not None:
                asyncio.run_coroutine_threadsafe(
                    self.asr.open_audio_channels(self), self.loop
                )
                self.logger.bind(tag=TAG).debug("Đã mở kênh nhận dạng giọng nói")
            else:
                self.logger.bind(tag=TAG).warning("Không thể khởi tạo ASR")

            if self.tts is None:
                self.logger.bind(tag=TAG).debug("Đang khởi tạo mô-đun TTS")
                self._initialize_tts()
            else:
                self.logger.bind(tag=TAG).debug("TTS tái sử dụng từ cache")

            if self.tts is not None:
                asyncio.run_coroutine_threadsafe(
                    self.tts.open_audio_channels(self), self.loop
                )
                self.logger.bind(tag=TAG).debug("Đã mở kênh tổng hợp giọng nói")
            else:
                self.logger.bind(tag=TAG).warning("Không thể khởi tạo TTS")

            self._initialize_memory()
            self._initialize_intent()
            self._init_report_threads()

            # _init_prompt_enhancement is now async, schedule it
            asyncio.run_coroutine_threadsafe(self._init_prompt_enhancement(), self.loop)

            elapsed = time.perf_counter() - start_ts
            self.logger.bind(tag=TAG).debug(
                f"Hoàn tất khởi tạo pipeline âm thanh sau {elapsed:.2f}s"
            )

        except Exception as e:
            stack_trace = traceback.format_exc()
            self.logger.bind(tag=TAG).error(
                f"Khởi tạo thành phần thất bại: {e}\n{stack_trace}"
            )
        finally:
            # Đánh dấu pipeline sẵn sàng giống hành vi cũ (không reset VAD tại đây)
            self._signal_components_ready()

    def _signal_components_ready(self):
        """Đánh dấu pipeline âm thanh đã sẵn sàng theo cách thread-safe."""

        def _set_ready():
            if not self.components_ready.is_set():
                self.components_ready.set()
                self.logger.bind(tag=TAG).info(
                    "ASR/VAD/TTS đã sẵn sàng xử lý audio đầu tiên"
                )

        loop = getattr(self, "loop", None)
        if loop and loop.is_running():
            try:
                loop.call_soon_threadsafe(_set_ready)
            except RuntimeError:
                _set_ready()
        else:
            _set_ready()

    async def wait_for_pipeline_ready(self, timeout: Optional[float] = None) -> bool:
        """
        Chờ pipeline âm thanh sẵn sàng. Trả về True nếu thành công, False nếu hết thời gian.
        """
        try:
            if timeout is None:
                await self.components_ready.wait()
            else:
                await asyncio.wait_for(self.components_ready.wait(), timeout)
            return True
        except asyncio.TimeoutError:
            self.logger.bind(tag=TAG).warning(
                f"Hết thời gian chờ pipeline âm thanh (timeout={timeout}s)"
            )
            return False

    async def _init_prompt_enhancement(self):
        """Khởi tạo prompt enhancement (async)

        Xây dựng full prompt với user_profile và context
        """
        try:
            # Update context (location, weather)
            await self.prompt_manager.update_context_info(self, self.client_ip)

            # Build enhanced prompt với user_profile
            enhanced_prompt = await self.prompt_manager.build_enhanced_prompt(
                user_prompt=self.config.get("prompt", ""),
                device_id=self.device_id,
                client_ip=self.client_ip,
                user_profile=self.agent.get("user_profile"),
            )

            if enhanced_prompt:
                self.change_system_prompt(enhanced_prompt)
                self.logger.bind(tag=TAG).debug(
                    "Đã xây dựng system prompt với user_profile thành công"
                )
            else:
                self.logger.bind(tag=TAG).warning("build_enhanced_prompt trả về rỗng")

        except Exception as e:
            self.logger.bind(tag=TAG).error(f"Lỗi khi xây dựng enhanced prompt: {e}")

    def _init_report_threads(self):
        """Khởi tạo các luồng báo cáo ASR/TTS"""
        self.logger.bind(tag=TAG).debug(
            f"chat_history_conf: {self.chat_history_conf}, read_config_from_api: {self.read_config_from_api}"
        )
        if not self.read_config_from_api:
            return
        if self.chat_history_conf == 0:
            self.logger.bind(tag=TAG).debug(
                "chat_history_conf == 0, không khởi động luồng báo cáo"
            )
            return
        if self.report_thread is None or not self.report_thread.is_alive():
            self.report_thread = threading.Thread(
                target=self._report_worker, daemon=True
            )
            self.report_thread.start()
            self.logger.bind(tag=TAG).info("Đã khởi động luồng báo cáo TTS/ASR")

    def _initialize_tts(self):
        """Khởi tạo TTS"""
        self.tts = initialize_tts_component(
            conn=self,
            config=self.config,
            logger_instance=self.logger,
        )

    def _initialize_asr(self):
        """Khởi tạo ASR"""
        self.asr = initialize_asr_component(
            conn=self,
            config=self.config,
            logger_instance=self.logger,
        )

    def _initialize_voiceprint(self):
        """Khởi tạo voiceprint cho kết nối hiện tại"""
        initialize_voiceprint_component(
            conn=self,
            config=self.config,
            logger_instance=self.logger,
        )

    def _initialize_agent_module(self):
        """Load agent_info từ auth state, bỏ qua nếu không có

        Thực hiện:
        1. Load modules từ providers (DB) hoặc agent_template (config.yml fallback)
        2. Áp dụng config fields (prompt, voiceprint, etc.)
        3. Gán modules vào connection
        """
        self.logger.bind(tag=TAG).debug(f"agent: {self.agent}")
        agent_template = self.agent.get("template")

        if not self.read_config_from_api or agent_template is None:
            self.logger.bind(tag=TAG).debug("Không khởi tạo cấu hình private từ API")
            return
        self.logger.bind(tag=TAG).info(
            f"Khởi tạo cấu hình private từ API: {agent_template}"
        )

        # Load modules - ưu tiên từ providers (DB), fallback config.yml
        try:
            providers = self.agent.get("providers", {})
            summary_memory = agent_template.get("summary_memory")

            # Debug log providers
            self.logger.bind(tag=TAG).debug(
                f"[PROVIDER DEBUG] providers from agent: {list(providers.keys()) if providers else 'None'}"
            )
            for cat, prov in (providers or {}).items():
                if prov:
                    self.logger.bind(tag=TAG).debug(
                        f"[PROVIDER DEBUG] {cat}: id={prov.get('id')}, name={prov.get('name')}, type={prov.get('type')}"
                    )

            # Check có provider nào có config không
            has_valid_provider = providers and any(
                p is not None and p.get("config") for p in providers.values()
            )

            if has_valid_provider:
                # Có ít nhất 1 provider từ DB có config -> dùng load_modules_from_providers
                self.logger.bind(tag=TAG).info(
                    "🗄️ Khởi tạo modules từ DATABASE providers"
                )
                modules = load_modules_from_providers(
                    providers=providers,
                    config=self.config,
                    logger_instance=self.logger,
                    summary_memory=summary_memory,
                    agent_template=agent_template,
                )
            else:
                # Không có provider -> fallback về config.yml (legacy)
                self.logger.bind(tag=TAG).info(
                    "📄 Khởi tạo modules từ CONFIG.YML (no DB providers)"
                )
                modules = load_modules_from_agent(
                    self.config, agent_template, self.logger
                )

            self.logger.bind(tag=TAG).info(f"Modules loaded: {list(modules.keys())}")
        except Exception as e:
            self.logger.bind(tag=TAG).error(
                f"Khởi tạo thành phần thất bại: {e}", exc_info=True
            )
            modules = {}

        # Áp dụng config fields (prompt, voiceprint, device_max_output_size, etc.)
        self.config = apply_agent_config_fields(
            agent_template, self.config, self, self.logger
        )

        # Gán modules vào connection (không async ở đây)
        # Note: Không thể gọi open_audio_channels ở sync context
        # Sẽ được xử lý trong _initialize_components()
        for module_type, module_instance in modules.items():
            if module_instance is not None:
                attr_name = module_type.lower()
                if hasattr(self, attr_name):
                    setattr(self, attr_name, module_instance)
                    self.logger.bind(tag=TAG).debug(
                        f"✅ Assigned {module_type} module from agent_template"
                    )

    def _initialize_memory(self):
        """Khởi tạo mô-đun trí nhớ"""
        initialize_memory_component(
            conn=self,
            config=self.config,
            logger_instance=self.logger,
        )

    def _initialize_intent(self):
        """Khởi tạo mô-đun nhận diện ý định"""
        initialize_intent_component(
            conn=self,
            config=self.config,
            logger_instance=self.logger,
        )

        # Nạp trình xử lý công cụ thống nhất (nếu cần)
        if self.load_function_plugin:
            # Lấy tool_refs từ Intent provider config hoặc fallback
            tool_refs = self._get_tool_refs_from_intent()

            self.func_handler = UnifiedToolHandler(self, tool_refs=tool_refs)
            if hasattr(self, "loop") and self.loop:
                asyncio.run_coroutine_threadsafe(
                    self.func_handler._initialize(), self.loop
                )

    def _get_tool_refs_from_intent(self) -> list[str] | None:
        """
        Lấy danh sách tool references từ Intent provider config.

        Priority:
        1. Intent provider từ DATABASE (self.agent["providers"]["Intent"])
        2. Intent provider từ config.yml (self.config["Intent"][selected])
        3. AgentTemplate.tools (backward compatibility)
        4. None (fallback về config["Intent"]["functions"] trong UnifiedToolHandler)
        """
        # 1. Ưu tiên cao nhất: Lấy từ DB provider (nếu có)
        if self.agent:
            providers = self.agent.get("providers", {})
            intent_provider = providers.get("Intent")
            if intent_provider and isinstance(intent_provider, dict):
                intent_config = intent_provider.get("config", {})
                functions = intent_config.get("functions")
                if functions:
                    self.logger.bind(tag=TAG).debug(
                        f"Tool refs từ Intent provider (DB): {functions}"
                    )
                    return functions

        # 2. Fallback: Lấy từ config.yml Intent
        intent_config = self.config.get("Intent", {})
        selected_intent = self.config.get("selected_module", {}).get("Intent")

        if selected_intent and selected_intent in intent_config:
            functions = intent_config[selected_intent].get("functions")
            if functions:
                self.logger.bind(tag=TAG).debug(
                    f"Tool refs từ Intent provider (config.yml): {functions}"
                )
                return functions

        # 3. Fallback: AgentTemplate.tools (backward compatibility)
        agent_template = self.agent.get("template") if self.agent else None
        if agent_template:
            tools = agent_template.get("tools")
            if tools:
                self.logger.bind(tag=TAG).debug(
                    f"Tool refs từ AgentTemplate.tools: {tools}"
                )
                return tools

        # 4. Return None để UnifiedToolHandler fallback về config["Intent"]["functions"]
        return None

    def change_system_prompt(self, prompt):
        self.prompt = prompt
        self.dialogue.update_system_message(self.prompt)

    async def _cleanup_modules(self):
        """Cleanup all AI modules to prepare for reload."""
        modules_to_close = [
            ("TTS", self.tts),
            ("ASR", self.asr),
            ("VAD", self.vad),
            ("LLM", self.llm),
            ("Memory", self.memory),
            ("Intent", self.intent),
        ]

        for name, module in modules_to_close:
            if module is None or not hasattr(module, "close"):
                continue

            try:
                if asyncio.iscoroutinefunction(module.close):
                    await module.close()
                else:
                    if self.thread_pool:
                        await self.thread_pool.run_blocking(module.close)
                    else:
                        await asyncio.to_thread(module.close)
            except Exception as e:
                self.logger.bind(tag=TAG).warning(f"Failed to cleanup {name}: {e}")

        # Clear buffers and reset states
        try:
            self.client_audio_buffer.clear()
            self.asr_audio.clear()
            self.reset_vad_states()
        except Exception as e:
            self.logger.bind(tag=TAG).warning(f"Failed to clear buffers: {e}")

    async def reload_agent_template(
        self, new_agent: Dict[str, Any], providers: Dict[str, Any] | None = None
    ):
        """Tải lại template agent từ agent_info mới

        Flow:
        1. Cleanup modules cũ
        2. Load modules mới từ providers (DB) hoặc agent_info (config.yml fallback)
        3. Áp dụng modules và config fields
        4. Re-initialize memory và intent
        5. Nếu lỗi: rollback các modules cũ

        Args:
            new_agent: Template dict mới
            providers: Provider configs từ DB (optional, nếu None thì fallback config.yml)
        """
        old_modules = {}
        self.reloading = True
        new_config = copy.deepcopy(self.config)

        try:
            # Phase 1: Cleanup old modules
            await self._cleanup_modules()

            try:
                # Phase 2: Load new modules - ưu tiên providers nếu có
                if providers and any(p is not None for p in providers.values()):
                    summary_memory = new_agent.get("summary_memory")
                    modules = load_modules_from_providers(
                        providers=providers,
                        config=new_config,
                        logger_instance=self.logger,
                        summary_memory=summary_memory,
                    )
                    self.logger.bind(tag=TAG).info(
                        "Reload modules từ database providers"
                    )
                else:
                    modules = load_modules_from_agent(
                        new_config, new_agent, self.logger
                    )
                    self.logger.bind(tag=TAG).info("Reload modules từ config.yml")

                # Phase 3a: Apply modules with async operations (audio channels, etc.)
                new_config, old_modules = await apply_agent_modules(
                    agent_config=new_agent,
                    conn=self,
                    base_config=new_config,
                    modules_dict=modules,
                    logger=self.logger,
                )

                # Phase 3b: Apply config fields (prompt, voiceprint, etc.)
                new_config = apply_agent_config_fields(
                    new_agent, new_config, self, self.logger
                )

            except Exception as module_error:
                self.logger.bind(tag=TAG).error(
                    f"Module loading/applying failed: {module_error}", exc_info=True
                )
                raise

            # Phase 4: Re-initialize memory and intent
            try:
                self._initialize_memory()
                # set intent and function plugin to None before re-init
                self.load_function_plugin = None
                self._initialize_intent()
            except Exception as init_error:
                self.logger.bind(tag=TAG).warning(
                    f"Memory/Intent init warning: {init_error}"
                )

            # Phase 5: Complete reload
            self.components_ready.set()
            self.config = new_config
            # Update template, nhưng giữ nguyên user_profile từ agent cũ
            self.agent["template"] = new_agent
            # Cập nhật prompt enhancement mới (user_profile vẫn từ self.agent cũ)
            asyncio.run_coroutine_threadsafe(self._init_prompt_enhancement(), self.loop)
            self.logger.bind(tag=TAG).info("Hot-reload completed")

        except Exception as e:
            self.logger.bind(tag=TAG).error(f"Hot-reload failed: {e}", exc_info=True)
            # Rollback: Restore old modules
            try:
                for attr_name, old_module in old_modules.items():
                    setattr(self, attr_name, old_module)
                self.components_ready.set()
                self.logger.bind(tag=TAG).info("Rollback completed")
            except Exception as rollback_error:
                self.logger.bind(tag=TAG).critical(
                    f"Rollback failed: {rollback_error}", exc_info=True
                )
        finally:
            self.reloading = False

    def chat(self, query, depth=0):
        self.logger.bind(tag=TAG).debug(
            f"Mô hình nhận được tin nhắn từ người dùng: {query}"
        )
        self.llm_finish_task = False

        if depth == 0:
            self.sentence_id = str(uuid.uuid4().hex)
            self.dialogue.put(Message(role="user", content=query))
            self.tts.tts_text_queue.put(
                TTSMessageDTO(
                    sentence_id=self.sentence_id,
                    sentence_type=SentenceType.FIRST,
                    content_type=ContentType.ACTION,
                )
            )

        functions = None
        if self.intent_type == "function_call" and hasattr(self, "func_handler"):
            functions = self.func_handler.get_functions()
        response_message = []

        try:
            memory_str = None
            # Chỉ query memory khi depth == 0 (user query ban đầu)
            # Không query với tool result để tránh delay từ embeddings API
            if self.memory is not None and depth == 0:
                future = asyncio.run_coroutine_threadsafe(
                    self.memory.query_memory(query), self.loop
                )
                memory_str = future.result()

            if self.intent_type == "function_call" and functions is not None:
                llm_responses = self.llm.response_with_functions(
                    self.session_id,
                    self.dialogue.get_llm_dialogue_with_memory(
                        memory_str, self.config.get("voiceprint", {})
                    ),
                    functions=functions,
                )
            else:
                llm_responses = self.llm.response(
                    self.session_id,
                    self.dialogue.get_llm_dialogue_with_memory(
                        memory_str, self.config.get("voiceprint", {})
                    ),
                )
        except Exception as e:
            self.logger.bind(tag=TAG).error(f"LLM gặp lỗi khi xử lý {query}: {e}")
            return None
        self.logger.bind(tag=TAG).debug("Bắt đầu xử lý phản hồi từ LLM")
        tool_call_flag = False
        function_name = None
        function_id = None
        function_arguments = ""
        content_arguments = ""
        self.client_abort = False
        emotion_flag = True
        for response in llm_responses:
            if self.client_abort:
                break
            if self.intent_type == "function_call" and functions is not None:
                content, tools_call = response
                if "content" in response:
                    content = response["content"]
                    tools_call = None
                if content is not None and len(content) > 0:
                    content_arguments += content

                if not tool_call_flag and content_arguments.startswith("<tool_call>"):
                    tool_call_flag = True

                if tools_call is not None and len(tools_call) > 0:
                    tool_call_flag = True
                    if tools_call[0].id is not None and tools_call[0].id != "":
                        function_id = tools_call[0].id
                    if (
                        tools_call[0].function.name is not None
                        and tools_call[0].function.name != ""
                    ):
                        function_name = tools_call[0].function.name
                    if tools_call[0].function.arguments is not None:
                        function_arguments += tools_call[0].function.arguments
            else:
                content = response

            if emotion_flag and content is not None and content.strip():
                asyncio.run_coroutine_threadsafe(
                    textUtils.get_emotion(self, content),
                    self.loop,
                )
                emotion_flag = False

            if content is not None and len(content) > 0:
                if not tool_call_flag:
                    response_message.append(content)
                    self.tts.tts_text_queue.put(
                        TTSMessageDTO(
                            sentence_id=self.sentence_id,
                            sentence_type=SentenceType.MIDDLE,
                            content_type=ContentType.TEXT,
                            content_detail=content,
                        )
                    )

        if tool_call_flag:
            bHasError = False
            if function_id is None:
                a = extract_json_from_string(content_arguments)
                if a is not None:
                    try:
                        content_arguments_json = json.loads(a)
                        function_name = content_arguments_json["name"]
                        function_arguments = json.dumps(
                            content_arguments_json["arguments"], ensure_ascii=False
                        )
                        function_id = str(uuid.uuid4().hex)
                    except Exception:
                        bHasError = True
                        response_message.append(a)
                else:
                    bHasError = True
                    response_message.append(content_arguments)
                if bHasError:
                    self.logger.bind(tag=TAG).error(
                        f"function call error: {content_arguments}"
                    )
            if not bHasError:
                if len(response_message) > 0:
                    text_buff = "".join(response_message)
                    # Only add to dialogue if text has actual content (not just whitespace)
                    if text_buff.strip():
                        self.tts_MessageText = text_buff
                        self.dialogue.put(Message(role="assistant", content=text_buff))
                response_message.clear()
                self.logger.bind(tag=TAG).debug(
                    f"function_name={function_name}, function_id={function_id}, function_arguments={function_arguments}"
                )
                function_call_data = {
                    "name": function_name,
                    "id": function_id,
                    "arguments": function_arguments,
                }

                result = asyncio.run_coroutine_threadsafe(
                    self.func_handler.handle_llm_function_call(
                        self, function_call_data
                    ),
                    self.loop,
                ).result()
                self._handle_function_result(result, function_call_data, depth=depth)

        if len(response_message) > 0:
            text_buff = "".join(response_message)
            # Only add to dialogue if text has actual content (not just whitespace)
            if text_buff.strip():
                self.tts_MessageText = text_buff
                self.dialogue.put(Message(role="assistant", content=text_buff))
        if depth == 0:
            self.tts.tts_text_queue.put(
                TTSMessageDTO(
                    sentence_id=self.sentence_id,
                    sentence_type=SentenceType.LAST,
                    content_type=ContentType.ACTION,
                )
            )
        self.llm_finish_task = True
        self.logger.bind(tag=TAG).debug(
            json.dumps(self.dialogue.get_llm_dialogue(), indent=4, ensure_ascii=False)
        )

        return True

    def _handle_function_result(
        self, result: ActionResponse, function_call_data, depth
    ):
        # Import Action từ plugins
        try:
            from app.ai.plugins_func.register import Action
        except ImportError:
            # Fallback nếu không có plugins_func
            class Action:
                RESPONSE = "response"
                REQLLM = "reqllm"
                NOTFOUND = "notfound"
                ERROR = "error"

        if result.action == Action.RESPONSE:
            text = result.response
            self.tts.tts_one_sentence(self, ContentType.TEXT, content_detail=text)
            self.dialogue.put(Message(role="assistant", content=text))
        elif result.action == Action.REQLLM:
            text = result.result
            if text is not None and len(text) > 0:
                function_id = function_call_data["id"]
                function_name = function_call_data["name"]
                function_arguments = function_call_data["arguments"]
                self.dialogue.put(
                    Message.create_tool_call(
                        function_id=function_id,
                        function_name=function_name,
                        function_arguments=function_arguments,
                    )
                )
                self.dialogue.put(
                    Message.create_tool_response(
                        tool_call_id=function_id,
                        content=text,
                    )
                )
                self.chat(text, depth=depth + 1)
        elif result.action == Action.NOTFOUND or result.action == Action.ERROR:
            text = result.response if result.response else result.result
            self.tts.tts_one_sentence(self, ContentType.TEXT, content_detail=text)
            self.dialogue.put(Message(role="assistant", content=text))
        else:
            pass

    def _report_worker(self):
        """Worker báo cáo lịch sử trò chuyện"""
        while not self.stop_event.is_set():
            try:
                item = self.report_queue.get(timeout=1)
                if item is None:
                    break
                try:
                    # Use thread_pool nếu có, nếu không thì chạy trực tiếp
                    if self.thread_pool:
                        # Wrap _process_report trong async function
                        async def run_report():
                            await self.thread_pool.run_blocking(
                                self._process_report, *item
                            )

                        asyncio.run_coroutine_threadsafe(run_report(), self.loop)
                    else:
                        self._process_report(*item)
                except Exception as e:
                    self.logger.bind(tag=TAG).error(
                        f"Lỗi trong luồng báo cáo lịch sử: {e}"
                    )
            except queue.Empty:
                continue
            except Exception as e:
                self.logger.bind(tag=TAG).error(f"Lỗi worker báo cáo lịch sử: {e}")

        self.logger.bind(tag=TAG).info("Luồng báo cáo lịch sử đã dừng")

    def _process_report(self, type, text, audio_data, report_time):
        """Xử lý tác vụ báo cáo"""
        try:
            report(self, type, text, audio_data, report_time)
        except Exception as e:
            self.logger.bind(tag=TAG).error(f"Lỗi khi xử lý báo cáo: {e}")
        finally:
            self.report_queue.task_done()

    def clearSpeakStatus(self):
        self.client_is_speaking = False
        self.logger.bind(tag=TAG).debug("Đã xóa trạng thái server đang nói")

    async def close(self, ws=None):
        """Dọn dẹp tài nguyên kết nối"""
        try:
            closing_ws = False
            if not self._closing:
                self._closing = True
                closing_ws = True

            if hasattr(self, "audio_buffer"):
                self.audio_buffer.clear()

            if self.timeout_task and not self.timeout_task.done():
                current_task = asyncio.current_task()
                self.timeout_task.cancel()
                if self.timeout_task is not current_task:
                    try:
                        await self.timeout_task
                    except asyncio.CancelledError:
                        pass
                self.timeout_task = None

            if hasattr(self, "func_handler") and self.func_handler:
                try:
                    await self.func_handler.cleanup()
                except Exception as cleanup_error:
                    self.logger.bind(tag=TAG).error(
                        f"Lỗi khi dọn tài nguyên tool handler: {cleanup_error}"
                    )

            # Cleanup FFmpeg streamer nếu đang chạy
            if hasattr(self, "current_streamer") and self.current_streamer:
                try:
                    self.current_streamer.stop()
                    self.current_streamer = None
                except Exception as streamer_error:
                    self.logger.bind(tag=TAG).error(
                        f"Lỗi khi dừng music streamer: {streamer_error}"
                    )

            if self.stop_event:
                self.stop_event.set()

            # Ngăn các luồng nền tiếp tục gửi dữ liệu sau khi kết nối đóng
            self.client_abort = True

            self.clear_queues()

            target_ws = ws or self.websocket
            try:
                if closing_ws and (
                    target_ws
                    and target_ws.application_state == WebSocketState.CONNECTED
                ):
                    await target_ws.close()
            except RuntimeError as ws_error:
                # Có thể đã gửi thông điệp đóng trước đó, ghi log mức debug và bỏ qua
                self.logger.bind(tag=TAG).debug(
                    f"WebSocket đã được đóng trước đó: {ws_error}"
                )
            except Exception as ws_error:
                self.logger.bind(tag=TAG).error(f"Lỗi khi đóng WebSocket: {ws_error}")
            finally:
                if closing_ws and target_ws:
                    self.websocket = None

            if self.tts:
                await self.tts.close()

            # REMOVED: Không còn executor để shutdown, thread_pool được quản lý bởi server

            self.logger.bind(tag=TAG).info("Đã giải phóng tài nguyên kết nối")
        except Exception as e:
            self.logger.bind(tag=TAG).error(f"Lỗi khi đóng kết nối: {e}")
        finally:
            if self.stop_event:
                self.stop_event.set()

    def clear_queues(self):
        """Dọn sạch toàn bộ hàng đợi tác vụ"""
        if self.tts:
            self.logger.bind(tag=TAG).debug(
                f"Bắt đầu dọn: hàng đợi TTS={self.tts.tts_text_queue.qsize()}, hàng đợi âm thanh={self.tts.tts_audio_queue.qsize()}"
            )

            for q in [
                self.tts.tts_text_queue,
                self.tts.tts_audio_queue,
                self.report_queue,
            ]:
                if not q:
                    continue
                while True:
                    try:
                        q.get_nowait()
                    except queue.Empty:
                        break

            self.logger.bind(tag=TAG).debug(
                f"Kết thúc dọn: hàng đợi TTS={self.tts.tts_text_queue.qsize()}, hàng đợi âm thanh={self.tts.tts_audio_queue.qsize()}"
            )

    def reset_vad_states(self, _preserve_manual: Optional[bool] = None):
        """Đặt lại bộ đệm/flag VAD (giữ nguyên như logic cũ)."""
        self.client_audio_buffer = bytearray()
        self.client_have_voice = False
        self.client_voice_stop = False
        self.logger.bind(tag=TAG).debug("VAD states reset.")

    def chat_and_close(self, text):
        """Chat with the user and then close the connection"""
        try:
            self.chat(text)
            self.close_after_chat = True
        except Exception as e:
            self.logger.bind(tag=TAG).error(f"Chat and close error: {str(e)}")

    async def _check_timeout(self):
        """Kiểm tra timeout của kết nối"""
        try:
            while not self.stop_event.is_set():
                if self.last_activity_time > 0.0:
                    current_time = time.time() * 1000
                    if (
                        current_time - self.last_activity_time
                        > self.timeout_seconds * 1000
                    ):
                        if not self.stop_event.is_set():
                            self.logger.bind(tag=TAG).info(
                                "Kết nối quá thời gian, chuẩn bị đóng"
                            )
                            self.stop_event.set()
                            try:
                                await self.close(self.websocket)
                            except Exception as close_error:
                                self.logger.bind(tag=TAG).error(
                                    f"Lỗi khi đóng kết nối do timeout: {close_error}"
                                )
                        break
                await asyncio.sleep(10)
        except Exception as e:
            self.logger.bind(tag=TAG).error(f"Lỗi trong tác vụ kiểm tra timeout: {e}")
        finally:
            self.logger.bind(tag=TAG).info("Tác vụ kiểm tra timeout đã dừng")

    async def send_text(self, text: str):
        """Gửi thông điệp dạng text tới client"""
        target_ws = self.websocket
        if not target_ws:
            return
        if target_ws.application_state != WebSocketState.CONNECTED:
            return
        try:
            await target_ws.send_text(text)
        except (WebSocketDisconnect, RuntimeError) as ws_error:
            self.logger.bind(tag=TAG).debug(
                f"Bỏ qua gửi text vì kết nối đã đóng: {ws_error}"
            )
            self.client_abort = True
        except Exception as send_error:
            self.logger.bind(tag=TAG).warning(
                f"Lỗi khi gửi text trên WebSocket: {send_error}"
            )

    async def send_bytes(self, data: Union[bytes, bytearray, memoryview]):
        """Gửi thông điệp dạng bytes tới client"""
        target_ws = self.websocket
        if not target_ws:
            return
        if target_ws.application_state != WebSocketState.CONNECTED:
            return
        try:
            await target_ws.send_bytes(bytes(data))
        except (WebSocketDisconnect, RuntimeError) as ws_error:
            self.logger.bind(tag=TAG).debug(
                f"Bỏ qua gửi bytes vì kết nối đã đóng: {ws_error}"
            )
            self.client_abort = True
        except Exception as send_error:
            self.logger.bind(tag=TAG).warning(
                f"Lỗi khi gửi bytes trên WebSocket: {send_error}"
            )

    async def send_raw(
        self, data: Union[str, bytes, bytearray, memoryview, Dict[str, Any]]
    ):
        """Gửi raw data tới client, tự động phân biệt text/bytes"""
        if data is None or not self.websocket:
            return
        if isinstance(data, (bytes, bytearray, memoryview)):
            await self.send_bytes(data)
        elif isinstance(data, str):
            await self.send_text(data)
        else:
            await self.send_text(json.dumps(data, ensure_ascii=False))
