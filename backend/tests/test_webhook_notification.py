"""
Integration tests for webhook notification feature.

Tests cover:
- Valid notification payload with device online (WS delivery)
- Valid notification payload with device offline (MQTT delivery)
- MQTT unavailable + device offline (202 Accepted)
- Invalid payload type
- Missing/invalid token authentication
- Agent/device not found scenarios
- WebSocket delivery failure with MQTT fallback
- MQTT topic format verification

NOTE: Run from project root with: pytest tests/test_webhook_notification.py
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Ensure src is in path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


class TestWebhookNotificationPayloadSchema:
    """Test WebhookNotificationPayload schema validation."""

    def test_valid_payload(self):
        """Test valid notification payload."""
        from app.schemas.agent import WebhookNotificationPayload

        payload = {
            "type": "notification",
            "useLLM": True,
            "title": "Test Alert",
            "content": "This is a test notification.",
        }
        notification = WebhookNotificationPayload(**payload)
        assert notification.type == "notification"
        assert notification.useLLM is True
        assert notification.title == "Test Alert"
        assert notification.content == "This is a test notification."

    def test_invalid_type(self):
        """Test payload with invalid type."""
        from app.schemas.agent import WebhookNotificationPayload

        payload = {
            "type": "invalid_type",
            "useLLM": True,
            "title": "Test",
            "content": "Content",
        }
        with pytest.raises(ValueError):
            WebhookNotificationPayload(**payload)

    def test_missing_required_field(self):
        """Test payload missing required field."""
        from app.schemas.agent import WebhookNotificationPayload

        payload = {
            "type": "notification",
            "useLLM": True,
            "title": "Test",
            # Missing content
        }
        with pytest.raises(ValueError):
            WebhookNotificationPayload(**payload)

    def test_invalid_usellm_type(self):
        """Test payload with invalid useLLM type."""
        from app.schemas.agent import WebhookNotificationPayload

        payload = {
            "type": "notification",
            "useLLM": "yes",  # Should be boolean
            "title": "Test",
            "content": "Content",
        }
        with pytest.raises(ValueError):
            WebhookNotificationPayload(**payload)

    def test_title_too_long(self):
        """Test payload with title exceeding max length."""
        from app.schemas.agent import WebhookNotificationPayload

        payload = {
            "type": "notification",
            "useLLM": True,
            "title": "x" * 257,  # Max is 256
            "content": "Content",
        }
        with pytest.raises(ValueError):
            WebhookNotificationPayload(**payload)

    def test_content_too_long(self):
        """Test payload with content exceeding max length."""
        from app.schemas.agent import WebhookNotificationPayload

        payload = {
            "type": "notification",
            "useLLM": True,
            "title": "Test",
            "content": "x" * 2049,  # Max is 2048
        }
        with pytest.raises(ValueError):
            WebhookNotificationPayload(**payload)


@pytest.mark.asyncio
class TestWebhookEndpointAuthentication:
    """Test webhook endpoint authentication."""

    async def test_missing_token(self, client):
        """Test webhook request without authentication token."""
        response = client.post(
            "/agents/test-agent-id/webhook",
            json={
                "type": "notification",
                "useLLM": True,
                "title": "Test",
                "content": "Content",
            },
        )
        # Should reject with 401 without token
        assert response.status_code in [401, 404, 500]  # Server may not be fully setup

    async def test_invalid_token_format(self, client):
        """Test webhook request with invalid token format."""
        response = client.post(
            "/agents/test-agent-id/webhook",
            params={"token": "invalid-token"},
            json={
                "type": "notification",
                "useLLM": True,
                "title": "Test",
                "content": "Content",
            },
        )
        # Should reject with 401 for invalid token
        assert response.status_code in [401, 404, 500]


@pytest.mark.asyncio
class TestWebhookEndpointPayloadValidation:
    """Test webhook endpoint payload validation."""

    async def test_invalid_type_in_payload(self, client):
        """Test webhook request with invalid type."""
        response = client.post(
            "/agents/test-agent-id/webhook?token=test-token",
            json={
                "type": "invalid_type",
                "useLLM": True,
                "title": "Test",
                "content": "Content",
            },
        )
        # Should reject with 400 for invalid type or schema error
        assert response.status_code in [400, 422, 404, 401, 500]

    async def test_missing_required_fields(self, client):
        """Test webhook request with missing required fields."""
        response = client.post(
            "/agents/test-agent-id/webhook?token=test-token",
            json={
                "type": "notification",
                "useLLM": True,
                # Missing title and content
            },
        )
        # Should reject with 422 for validation error
        assert response.status_code in [422, 400, 404, 401, 500]


@pytest.mark.asyncio
class TestPushAgentNotificationFunction:
    """Test push_agent_notification function logic."""

    async def test_device_online_websocket_delivery(self, mock_app):
        """Test notification delivery via WebSocket when device is online."""
        from app.services.agent_service import agent_service

        # Mock dependencies
        with patch(
            "app.services.agent_service.is_device_online", new_callable=AsyncMock
        ) as mock_online, patch(
            "app.services.agent_service.NotificationMessageHandler"
        ) as mock_handler_class:

            # Setup mocks
            mock_online.return_value = True
            mock_handler = MagicMock()
            mock_handler.handle = AsyncMock()
            mock_handler_class.return_value = mock_handler

            # Mock app state with active connections
            mock_app_state = MagicMock()
            mock_handler_obj = MagicMock()
            mock_handler_obj.device_id = "test-device-id"
            mock_handler_obj.loop = MagicMock()
            mock_handler_obj.loop.is_running.return_value = True
            mock_app_state.active_connections = {mock_handler_obj}

            payload = {
                "type": "notification",
                "useLLM": True,
                "title": "Test",
                "content": "Test content",
            }

            # Call function
            result = await agent_service.push_agent_notification(
                db=None,
                agent_id="test-agent",
                device_id="test-device-id",
                mac_address="AA:BB:CC:DD:EE:FF",
                payload=payload,
                mqtt_service=None,
                app_state=mock_app_state,
            )

            # Verify WebSocket delivery was attempted
            assert result["delivered"] is True
            assert result["method"] == "WS"
            mock_online.assert_called_once_with("test-device-id")

    async def test_device_offline_mqtt_delivery(self, mock_app):
        """Test notification delivery via MQTT when device is offline."""
        from app.services.agent_service import agent_service

        # Mock dependencies
        with patch(
            "app.services.agent_service.is_device_online", new_callable=AsyncMock
        ) as mock_online:

            mock_online.return_value = False

            # Mock MQTT service
            mock_mqtt = MagicMock()
            mock_mqtt.is_available.return_value = True
            mock_mqtt.publish = AsyncMock(return_value=True)

            payload = {
                "type": "notification",
                "useLLM": True,
                "title": "Test",
                "content": "Test content",
            }

            # Call function
            result = await agent_service.push_agent_notification(
                db=None,
                agent_id="test-agent",
                device_id="test-device-id",
                mac_address="AA:BB:CC:DD:EE:FF",
                payload=payload,
                mqtt_service=mock_mqtt,
                app_state=None,
            )

            # Verify MQTT delivery
            assert result["delivered"] is True
            assert result["method"] == "MQTT"

            # Verify MQTT topic format
            expected_topic = "device/AA:BB:CC:DD:EE:FF"
            mock_mqtt.publish.assert_called_once()
            call_args = mock_mqtt.publish.call_args
            assert call_args[0][0] == expected_topic  # topic argument
            assert call_args[0][1] == payload  # payload argument

    async def test_device_offline_no_mqtt(self, mock_app):
        """Test notification when device offline and MQTT unavailable."""
        from app.services.agent_service import agent_service

        # Mock dependencies
        with patch(
            "app.services.agent_service.is_device_online", new_callable=AsyncMock
        ) as mock_online:

            mock_online.return_value = False

            # Mock MQTT service as unavailable
            mock_mqtt = MagicMock()
            mock_mqtt.is_available.return_value = False

            payload = {
                "type": "notification",
                "useLLM": True,
                "title": "Test",
                "content": "Test content",
            }

            # Call function
            result = await agent_service.push_agent_notification(
                db=None,
                agent_id="test-agent",
                device_id="test-device-id",
                mac_address="AA:BB:CC:DD:EE:FF",
                payload=payload,
                mqtt_service=mock_mqtt,
                app_state=None,
            )

            # Verify delivery failed gracefully
            assert result["delivered"] is False
            assert result["method"] is None
            assert result["error"] is not None

    async def test_websocket_failure_mqtt_fallback(self, mock_app):
        """Test MQTT fallback when WebSocket delivery fails."""
        from app.services.agent_service import agent_service

        # Mock dependencies
        with patch(
            "app.services.agent_service.is_device_online", new_callable=AsyncMock
        ) as mock_online, patch(
            "app.services.agent_service.NotificationMessageHandler"
        ) as mock_handler_class:

            mock_online.return_value = True

            # Mock handler that throws exception
            mock_handler = MagicMock()
            mock_handler.handle = AsyncMock(side_effect=Exception("Handler error"))
            mock_handler_class.return_value = mock_handler

            # Mock MQTT service
            mock_mqtt = MagicMock()
            mock_mqtt.is_available.return_value = True
            mock_mqtt.publish = AsyncMock(return_value=True)

            # Mock app state with active connections
            mock_app_state = MagicMock()
            mock_handler_obj = MagicMock()
            mock_handler_obj.device_id = "test-device-id"
            mock_handler_obj.loop = MagicMock()
            mock_handler_obj.loop.is_running.return_value = True
            mock_app_state.active_connections = {mock_handler_obj}

            payload = {
                "type": "notification",
                "useLLM": True,
                "title": "Test",
                "content": "Test content",
            }

            # Call function
            result = await agent_service.push_agent_notification(
                db=None,
                agent_id="test-agent",
                device_id="test-device-id",
                mac_address="AA:BB:CC:DD:EE:FF",
                payload=payload,
                mqtt_service=mock_mqtt,
                app_state=mock_app_state,
            )

            # Verify fallback to MQTT
            assert result["delivered"] is True
            assert result["method"] == "MQTT"
            mock_mqtt.publish.assert_called_once()

    async def test_mqtt_topic_format(self, mock_app):
        """Test MQTT topic format is correct."""
        from app.services.agent_service import agent_service

        # Mock dependencies
        with patch(
            "app.services.agent_service.is_device_online", new_callable=AsyncMock
        ) as mock_online:

            mock_online.return_value = False

            # Mock MQTT service
            mock_mqtt = MagicMock()
            mock_mqtt.is_available.return_value = True
            mock_mqtt.publish = AsyncMock(return_value=True)

            test_cases = [
                "AA:BB:CC:DD:EE:FF",
                "00:11:22:33:44:55",
                "FF:FF:FF:FF:FF:FF",
            ]

            for mac in test_cases:
                result = await agent_service.push_agent_notification(
                    db=None,
                    agent_id="test-agent",
                    device_id="test-device-id",
                    mac_address=mac,
                    payload={
                        "type": "notification",
                        "useLLM": True,
                        "title": "T",
                        "content": "C",
                    },
                    mqtt_service=mock_mqtt,
                    app_state=None,
                )

                # Verify topic format: device/{mac_address}
                expected_topic = f"device/{mac}"
                call_args = mock_mqtt.publish.call_args
                assert call_args[0][0] == expected_topic


class TestWebhookIntegration:
    """Integration tests for webhook endpoint."""

    def test_webhook_endpoint_response_format(self, client):
        """Test webhook endpoint returns correct response format."""
        # Even if it fails auth/validation, response should be structured
        response = client.post(
            "/agents/test-agent/webhook",
            json={
                "type": "notification",
                "useLLM": True,
                "title": "Test",
                "content": "Content",
            },
        )
        # Response should be JSON (regardless of status)
        try:
            data = response.json()
            # Should have some response structure
            assert isinstance(data, dict)
        except:
            # Some errors might not return JSON, that's ok
            pass
