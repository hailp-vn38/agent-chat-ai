"""
Tests cho MQTTService module.

Test coverage:
- MQTTService.from_config() với config đầy đủ
- MQTTService.from_config() với config rỗng (graceful degrade)
- MQTTService.is_available() return False khi không có config
- MQTTService.publish() skip silently khi không có config
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.config.settings import MQTTSettings
from app.services.mqtt_service import MQTTService, get_mqtt_service


class TestMQTTServiceFromConfig:
    """Test MQTTService.from_config() factory method."""

    def test_from_config_with_full_config(self):
        """Test tạo MQTTService với config đầy đủ."""
        config = MQTTSettings(
            url="mqtt://localhost:1883",
            username="testuser",
            password="testpass",
            keepalive=30,
        )

        service = MQTTService.from_config(config)

        assert service.config == config
        assert service.config.url == "mqtt://localhost:1883"
        assert service.config.username == "testuser"
        assert service.config.password == "testpass"
        assert service.config.keepalive == 30
        assert not service._started

    def test_from_config_with_none_config(self):
        """Test tạo MQTTService với config None (graceful degrade)."""
        service = MQTTService.from_config(None)

        assert service.config is None
        assert not service.is_available()

    def test_from_config_with_empty_url(self):
        """Test tạo MQTTService với URL rỗng (graceful degrade)."""
        config = MQTTSettings(url="")

        service = MQTTService.from_config(config)

        assert service.config is not None
        assert service.config.url == ""
        assert not service.is_available()


class TestMQTTServiceIsAvailable:
    """Test MQTTService.is_available() method."""

    def test_is_available_without_config(self):
        """Test is_available() trả về False khi không có config."""
        service = MQTTService(None)
        assert not service.is_available()

    def test_is_available_with_empty_url(self):
        """Test is_available() trả về False khi URL rỗng."""
        config = MQTTSettings(url="")
        service = MQTTService(config)
        assert not service.is_available()

    def test_is_available_not_started(self):
        """Test is_available() trả về False khi chưa start."""
        config = MQTTSettings(url="mqtt://localhost:1883")
        service = MQTTService(config)
        assert not service.is_available()

    @pytest.mark.asyncio
    async def test_is_available_after_start_with_valid_config(self):
        """Test is_available() trả về True sau khi start với config hợp lệ."""
        config = MQTTSettings(url="mqtt://localhost:1883")
        service = MQTTService(config)

        # Mock _initialize_client để không thực sự kết nối
        with patch.object(service, "_initialize_client", return_value=True):
            with patch.object(service, "_schedule_connect"):
                await service.start()

        assert service.is_available()


class TestMQTTServicePublish:
    """Test MQTTService.publish() method."""

    @pytest.mark.asyncio
    async def test_publish_skips_when_not_available(self):
        """Test publish() skip silently khi không có config."""
        service = MQTTService(None)

        result = await service.publish("test/topic", {"message": "hello"})

        assert result is False

    @pytest.mark.asyncio
    async def test_publish_skips_when_url_empty(self):
        """Test publish() skip silently khi URL rỗng."""
        config = MQTTSettings(url="")
        service = MQTTService(config)

        result = await service.publish("test/topic", {"message": "hello"})

        assert result is False

    @pytest.mark.asyncio
    async def test_publish_success(self):
        """Test publish() thành công khi có connection."""
        config = MQTTSettings(url="mqtt://localhost:1883")
        service = MQTTService(config)
        service._started = True

        # Mock client và connection
        mock_client = MagicMock()
        service._client = mock_client
        service._connected = asyncio.Event()
        service._connected.set()

        with patch("asyncio.to_thread", new_callable=AsyncMock) as mock_to_thread:
            result = await service.publish("test/topic", {"message": "hello"})

        assert result is True
        mock_to_thread.assert_called_once()


class TestMQTTServiceLifecycle:
    """Test MQTTService lifecycle (start/shutdown)."""

    @pytest.mark.asyncio
    async def test_start_with_no_config(self):
        """Test start() không throw khi không có config."""
        service = MQTTService(None)

        await service.start()

        assert not service._started

    @pytest.mark.asyncio
    async def test_start_is_idempotent(self):
        """Test start() là idempotent."""
        config = MQTTSettings(url="mqtt://localhost:1883")
        service = MQTTService(config)

        with patch.object(
            service, "_initialize_client", return_value=True
        ) as mock_init:
            with patch.object(service, "_schedule_connect"):
                await service.start()
                await service.start()  # Second call

        # _initialize_client chỉ được gọi 1 lần vì _started = True sau lần đầu
        assert service._started

    @pytest.mark.asyncio
    async def test_shutdown_cleans_up(self):
        """Test shutdown() cleanup tài nguyên."""
        config = MQTTSettings(url="mqtt://localhost:1883")
        service = MQTTService(config)
        service._started = True
        service._client = MagicMock()
        service._connected = asyncio.Event()
        service._connected.set()
        service._loop = asyncio.get_event_loop()

        with patch("asyncio.to_thread", new_callable=AsyncMock):
            await service.shutdown()

        assert service._client is None
        assert not service._started
        assert not service._connected.is_set()

    @pytest.mark.asyncio
    async def test_shutdown_without_client(self):
        """Test shutdown() không throw khi không có client."""
        service = MQTTService(None)

        await service.shutdown()

        assert not service._started


class TestMQTTServiceIsConnected:
    """Test MQTTService.is_connected() method."""

    def test_is_connected_false_by_default(self):
        """Test is_connected() trả về False mặc định."""
        service = MQTTService(None)
        assert not service.is_connected()

    def test_is_connected_true_when_event_set(self):
        """Test is_connected() trả về True khi event được set."""
        service = MQTTService(None)
        service._connected = asyncio.Event()
        service._connected.set()
        assert service.is_connected()


class TestGetMQTTService:
    """Test get_mqtt_service() dependency function."""

    def test_get_mqtt_service_returns_service(self):
        """Test get_mqtt_service() trả về service từ app_state."""
        mock_state = MagicMock()
        mock_service = MQTTService(None)
        mock_state.mqtt_service = mock_service

        result = get_mqtt_service(mock_state)

        assert result is mock_service

    def test_get_mqtt_service_returns_none(self):
        """Test get_mqtt_service() trả về None khi không có service."""
        mock_state = MagicMock(spec=[])  # Empty spec = no attributes

        result = get_mqtt_service(mock_state)

        assert result is None


class TestMQTTSettingsIntegration:
    """Test MQTTSettings integration với Settings class."""

    def test_mqtt_settings_defaults(self):
        """Test MQTTSettings có defaults đúng."""
        settings = MQTTSettings()

        assert settings.url == ""
        assert settings.username == ""
        assert settings.password == ""
        assert settings.keepalive == 60
        assert settings.reconnect_min_delay == 2
        assert settings.reconnect_max_delay == 30

    def test_mqtt_settings_with_mqtts_url(self):
        """Test MQTTSettings với mqtts:// URL."""
        settings = MQTTSettings(
            url="mqtts://secure.broker.com:8883",
            username="user",
            password="pass",
        )

        assert settings.url == "mqtts://secure.broker.com:8883"
        assert settings.username == "user"


class TestMQTTServiceInitializeClient:
    """Test MQTTService._initialize_client() internal method."""

    def test_initialize_client_parses_mqtt_url(self):
        """Test _initialize_client() parse URL đúng."""
        config = MQTTSettings(url="mqtt://broker.local:1884")
        service = MQTTService(config)

        with patch("paho.mqtt.client.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client

            result = service._initialize_client()

        assert result is True
        assert service._host == "broker.local"
        assert service._port == 1884
        assert service._is_secure is False

    def test_initialize_client_parses_mqtts_url(self):
        """Test _initialize_client() parse mqtts:// URL đúng."""
        config = MQTTSettings(url="mqtts://secure.broker.com:8883")
        service = MQTTService(config)

        with patch("paho.mqtt.client.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client

            result = service._initialize_client()

        assert result is True
        assert service._host == "secure.broker.com"
        assert service._port == 8883
        assert service._is_secure is True

    def test_initialize_client_uses_default_port(self):
        """Test _initialize_client() sử dụng default port khi không specify."""
        config = MQTTSettings(url="mqtt://broker.local")
        service = MQTTService(config)

        with patch("paho.mqtt.client.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client

            service._initialize_client()

        assert service._port == 1883  # Default MQTT port

    def test_initialize_client_returns_false_without_config(self):
        """Test _initialize_client() trả về False khi không có config."""
        service = MQTTService(None)

        result = service._initialize_client()

        assert result is False

    def test_initialize_client_returns_false_with_empty_url(self):
        """Test _initialize_client() trả về False khi URL rỗng."""
        config = MQTTSettings(url="")
        service = MQTTService(config)

        result = service._initialize_client()

        assert result is False

    def test_initialize_client_returns_false_with_invalid_url(self):
        """Test _initialize_client() trả về False khi URL không hợp lệ."""
        config = MQTTSettings(url="not-a-valid-url")
        service = MQTTService(config)

        result = service._initialize_client()

        assert result is False
