"""
MQTT Service - Dịch vụ MQTT tập trung với Dependency Injection.

Module này cung cấp `MQTTService` class độc lập để quản lý kết nối MQTT,
có thể tái sử dụng cho nhiều module khác nhau (reminder, notification, IoT, etc.).

Tính năng chính:
- Factory pattern với `from_config()` để tạo instance
- Graceful degradation: không throw error nếu thiếu config
- Auto-reconnect với exponential backoff
- Tích hợp FastAPI lifecycle (startup/shutdown)

Example usage:
    ```python
    # Tạo service từ config
    mqtt_service = MQTTService.from_config(settings.mqtt)

    # Tích hợp vào FastAPI
    app.state.mqtt_service = mqtt_service
    await mqtt_service.start()

    # Sử dụng trong code
    if mqtt_service.is_available():
        await mqtt_service.publish("topic/test", {"message": "hello"})

    # Cleanup khi shutdown
    await mqtt_service.shutdown()
    ```
"""

from __future__ import annotations

import asyncio
import json
import ssl
from typing import Any, Dict, Optional
from urllib.parse import urlparse

import paho.mqtt.client as mqtt

from app.config.settings import MQTTSettings
from app.core.logger import setup_logging

TAG = __name__


class MQTTService:
    """Dịch vụ MQTT tập trung có thể tái sử dụng.

    Class này quản lý kết nối MQTT với các tính năng:
    - Auto-reconnect khi mất kết nối
    - Graceful degradation (không throw error nếu không có config)
    - Thread-safe publish operations
    - Proper lifecycle management

    Attributes:
        config: MQTTSettings config object (có thể None nếu không có config)

    Example:
        ```python
        # Cách 1: Tạo từ config
        service = MQTTService.from_config(mqtt_settings)

        # Cách 2: Tạo trực tiếp
        service = MQTTService(mqtt_settings)

        # Kiểm tra khả dụng
        if service.is_available():
            await service.publish("topic", {"data": "value"})
        ```
    """

    def __init__(self, config: Optional[MQTTSettings] = None) -> None:
        """Khởi tạo MQTT service.

        Args:
            config: MQTTSettings config object. Nếu None, service sẽ hoạt động
                    ở chế độ "unavailable" (is_available() trả về False).
        """
        self.config = config
        self.logger = setup_logging()
        self._client: Optional[mqtt.Client] = None
        self._connected = asyncio.Event()
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._connect_task: Optional[asyncio.Task] = None
        self._closing = False
        self._started = False

        # Parsed connection info
        self._host: Optional[str] = None
        self._port: Optional[int] = None
        self._keepalive: int = 60
        self._is_secure = False

    @classmethod
    def from_config(cls, config: Optional[MQTTSettings] = None) -> "MQTTService":
        """Factory method để tạo MQTTService từ config.

        Đây là cách khuyên dùng để tạo instance. Nếu config là None hoặc
        không có URL, service sẽ hoạt động ở chế độ degraded (silent no-op).

        Args:
            config: MQTTSettings object hoặc None

        Returns:
            MQTTService instance

        Example:
            ```python
            # Từ Settings object
            service = MQTTService.from_config(settings.mqtt)

            # Không có config (degraded mode)
            service = MQTTService.from_config(None)
            ```
        """
        instance = cls(config)
        if not config or not config.url:
            instance.logger.bind(tag=TAG).warning(
                "MQTT config không được cấu hình, service sẽ hoạt động ở chế độ degraded"
            )
        return instance

    def _initialize_client(self) -> bool:
        """Khởi tạo MQTT client nội bộ.

        Returns:
            True nếu khởi tạo thành công, False nếu không có config hợp lệ
        """
        if self._client is not None:
            return True

        if not self.config or not self.config.url:
            return False

        url = urlparse(self.config.url)
        if not url.hostname:
            self.logger.bind(tag=TAG).warning(
                f"Không thể phân tích MQTT URL: {self.config.url}"
            )
            return False

        self._host = url.hostname
        self._is_secure = url.scheme in {"mqtts", "ssl", "tls"}
        default_port = 8883 if self._is_secure else 1883
        self._port = url.port or default_port
        self._keepalive = self.config.keepalive

        self.logger.bind(tag=TAG).debug(
            f"Khởi tạo MQTT client: {self._host}:{self._port} (secure={self._is_secure})"
        )

        client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2)
        client.on_connect = self._on_connect
        client.on_disconnect = self._on_disconnect

        if self.config.username:
            client.username_pw_set(self.config.username, self.config.password)

        if self._is_secure:
            client.tls_set(cert_reqs=ssl.CERT_REQUIRED)
            client.tls_insecure_set(False)

        client.reconnect_delay_set(
            min_delay=self.config.reconnect_min_delay,
            max_delay=self.config.reconnect_max_delay,
        )
        self._client = client
        return True

    async def start(self) -> None:
        """Khởi động MQTT service và bắt đầu kết nối.

        Method này là idempotent - gọi nhiều lần không có side effect.
        Nếu không có config hợp lệ, method sẽ return ngay mà không throw.
        """
        if self._started:
            return

        if not self._initialize_client():
            self.logger.bind(tag=TAG).info(
                "MQTT service không khởi động do không có config hợp lệ"
            )
            return

        self._started = True

        if self._loop is None:
            try:
                self._loop = asyncio.get_running_loop()
            except RuntimeError:
                self._loop = asyncio.new_event_loop()
                asyncio.set_event_loop(self._loop)

        self._schedule_connect()

    def _schedule_connect(self) -> None:
        """Lên lịch task kết nối MQTT."""
        if self._connect_task and not self._connect_task.done():
            return
        if self._loop is None:
            return
        self._connect_task = self._loop.create_task(self._connect())

    async def _connect(self) -> bool:
        """Thực hiện kết nối MQTT."""
        client = self._client
        if client is None or self._host is None or self._port is None:
            return False

        self._connected.clear()

        try:
            self.logger.bind(tag=TAG).debug(
                f"Đang kết nối MQTT tới {self._host}:{self._port}..."
            )
            await asyncio.to_thread(
                client.connect, self._host, self._port, self._keepalive
            )
            client.loop_start()
            await asyncio.wait_for(self._connected.wait(), timeout=10.0)
            self.logger.bind(tag=TAG).info(
                f"MQTT kết nối thành công tới {self._host}:{self._port}"
            )
            return True
        except asyncio.TimeoutError:
            self.logger.bind(tag=TAG).warning(
                f"MQTT kết nối tới {self._host}:{self._port} quá thời gian (timeout 10s)"
            )
        except ConnectionRefusedError as e:
            self.logger.bind(tag=TAG).warning(
                f"MQTT kết nối bị từ chối: {self._host}:{self._port} - {e}"
            )
        except Exception as exc:
            self.logger.bind(tag=TAG).warning(
                f"MQTT lỗi khi connect tới {self._host}:{self._port}: {exc}"
            )

        # Retry sau delay
        await asyncio.sleep(5)
        if not self._closing:
            self._schedule_connect()
        return False

    def _on_connect(
        self, client, userdata, connect_flags, rc, properties
    ):  # pragma: no cover - callback
        """Callback khi kết nối thành công."""
        if rc == 0:
            if self._loop:
                self._loop.call_soon_threadsafe(self._connected.set)
        else:
            self.logger.bind(tag=TAG).warning(f"MQTT kết nối thất bại, rc={rc}")

    def _on_disconnect(
        self, client, userdata, disconnect_flags, rc, properties
    ):  # pragma: no cover - callback
        """Callback khi mất kết nối."""
        if self._loop:
            self._loop.call_soon_threadsafe(self._connected.clear)
        if self._closing:
            return
        self.logger.bind(tag=TAG).warning("MQTT bị ngắt kết nối, thử kết nối lại")
        if self._loop:
            self._loop.call_soon_threadsafe(self._schedule_connect)

    def is_available(self) -> bool:
        """Kiểm tra MQTT service có sẵn sàng để sử dụng không.

        Returns:
            True nếu có config hợp lệ và đã khởi động, False nếu không

        Note:
            Method này chỉ kiểm tra config, không đảm bảo connection đang active.
            Để check connection, dùng `is_connected()`.
        """
        return bool(self.config and self.config.url and self._started)

    def is_connected(self) -> bool:
        """Kiểm tra MQTT đang kết nối.

        Returns:
            True nếu đang có connection active
        """
        return self._connected.is_set()

    async def _ensure_connection(self) -> bool:
        """Đảm bảo có connection trước khi publish."""
        if self._connected.is_set():
            return True

        if not self._started:
            await self.start()

        if not self._client:
            return False

        try:
            await asyncio.wait_for(self._connected.wait(), timeout=5.0)
            return True
        except asyncio.TimeoutError:
            return False

    async def publish(
        self,
        topic: str,
        payload: Dict[str, Any],
        qos: int = 1,
        retain: bool = False,
    ) -> bool:
        """Gửi message tới MQTT topic.

        Args:
            topic: MQTT topic để publish
            payload: Dict payload, sẽ được serialize thành JSON
            qos: Quality of Service level (0, 1, hoặc 2)
            retain: Có giữ message trên broker không

        Returns:
            True nếu publish thành công, False nếu không

        Note:
            Nếu service không available (không có config), method sẽ return
            False mà không throw exception (graceful degradation).
        """
        if not self.is_available():
            self.logger.bind(tag=TAG).debug(
                f"MQTT không khả dụng, bỏ qua publish tới {topic}"
            )
            return False

        client = self._client
        if not client:
            return False

        if not await self._ensure_connection():
            self.logger.bind(tag=TAG).warning(
                f"MQTT chưa sẵn sàng, không thể publish tới {topic}"
            )
            return False

        message = json.dumps(payload, ensure_ascii=False)

        try:
            await asyncio.to_thread(client.publish, topic, message, qos, retain)
            self.logger.bind(tag=TAG).debug(f"Đã publish MQTT message tới {topic}")
            return True
        except Exception as exc:
            self.logger.bind(tag=TAG).error(f"Lỗi khi publish MQTT ({topic}): {exc}")
            return False

    async def shutdown(self) -> None:
        """Dừng MQTT service và giải phóng tài nguyên.

        Method này là idempotent - gọi nhiều lần không có side effect.
        """
        self._closing = True
        client = self._client

        if not client:
            self._started = False
            return

        try:
            # Cancel connect task nếu đang chạy
            if self._connect_task and not self._connect_task.done():
                self._connect_task.cancel()
                try:
                    await self._connect_task
                except asyncio.CancelledError:
                    pass

            # Dừng loop và disconnect với timeout
            try:
                await asyncio.wait_for(asyncio.to_thread(client.loop_stop), timeout=2.0)
                await asyncio.wait_for(
                    asyncio.to_thread(client.disconnect), timeout=2.0
                )
            except asyncio.TimeoutError:
                self.logger.bind(tag=TAG).warning("MQTT disconnect timeout")

            self.logger.bind(tag=TAG).info("MQTT service đã shutdown")
        except Exception as exc:
            self.logger.bind(tag=TAG).warning(f"Lỗi khi shutdown MQTT service: {exc}")
        finally:
            self._connected.clear()
            self._client = None
            self._connect_task = None
            self._loop = None
            self._closing = False
            self._started = False


def get_mqtt_service(app_state) -> Optional[MQTTService]:
    """Dependency function để lấy MQTTService từ app.state.

    Args:
        app_state: FastAPI app.state object

    Returns:
        MQTTService instance hoặc None nếu không có

    Example:
        ```python
        @router.post("/notify")
        async def send_notification(
            request: Request,
            mqtt: MQTTService = Depends(lambda: get_mqtt_service(request.app.state))
        ):
            if mqtt and mqtt.is_available():
                await mqtt.publish("notifications", {"msg": "hello"})
        ```
    """
    return getattr(app_state, "mqtt_service", None)
