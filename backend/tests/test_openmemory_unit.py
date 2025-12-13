"""
Unit tests for OpenMemory provider local mode.
Tests the _build_embeddings_config method and initialization logic.
"""

import pytest
from unittest.mock import MagicMock, patch
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from app.ai.providers.memory.openmemory.openmemory import MemoryProvider


class TestBuildEmbeddingsConfig:
    """Test _build_embeddings_config method."""

    def test_synthetic_provider(self):
        """Test synthetic embeddings config."""
        config = {
            "mode": "local",
            "embeddings_provider": "synthetic",
        }
        provider = MemoryProvider(config)
        result = provider._build_embeddings_config()

        assert result == {"provider": "synthetic"}

    def test_openai_provider_with_model(self):
        """Test OpenAI embeddings config with model."""
        config = {
            "mode": "local",
            "embeddings_provider": "openai",
            "embeddings_api_key": "sk-abc123",
            "embeddings_model": "text-embedding-3-small",
        }
        provider = MemoryProvider(config)
        result = provider._build_embeddings_config()

        assert result["provider"] == "openai"
        assert result["apiKey"] == "sk-abc123"
        assert result["model"] == "text-embedding-3-small"

    def test_openai_provider_without_model(self):
        """Test OpenAI embeddings config without model."""
        config = {
            "mode": "local",
            "embeddings_provider": "openai",
            "embeddings_api_key": "sk-test",
        }
        provider = MemoryProvider(config)
        result = provider._build_embeddings_config()

        assert result["provider"] == "openai"
        assert result["apiKey"] == "sk-test"
        assert "model" not in result

    def test_gemini_provider_with_model(self):
        """Test Gemini embeddings config with model."""
        config = {
            "mode": "local",
            "embeddings_provider": "gemini",
            "embeddings_api_key": "AIza-xyz",
            "embeddings_model": "embedding-001",
        }
        provider = MemoryProvider(config)
        result = provider._build_embeddings_config()

        assert result["provider"] == "gemini"
        assert result["apiKey"] == "AIza-xyz"
        assert result["model"] == "embedding-001"

    def test_gemini_provider_without_model(self):
        """Test Gemini embeddings config without model."""
        config = {
            "mode": "local",
            "embeddings_provider": "gemini",
            "embeddings_api_key": "AIza-test",
        }
        provider = MemoryProvider(config)
        result = provider._build_embeddings_config()

        assert result["provider"] == "gemini"
        assert result["apiKey"] == "AIza-test"
        assert "model" not in result

    def test_default_synthetic_provider(self):
        """Test default embeddings provider is synthetic."""
        config = {"mode": "local"}
        provider = MemoryProvider(config)
        result = provider._build_embeddings_config()

        assert result == {"provider": "synthetic"}


class TestProviderInitialization:
    """Test provider initialization logic."""

    def test_local_mode_initialization(self):
        """Test local mode stores correct values."""
        config = {
            "mode": "local",
            "local_path": "./test.sqlite",
            "tier": "fast",
            "k": 5,
            "max_tokens": 3000,
        }
        provider = MemoryProvider(config)

        assert provider.mode == "local"
        assert provider.k == 5
        assert provider.max_tokens == 3000
        assert provider._client is None
        assert provider._client_initialized is False

    def test_remote_mode_initialization(self):
        """Test remote mode stores correct values."""
        config = {
            "mode": "remote",
            "base_url": "http://test:8080",
            "api_key": "test-key",
            "k": 3,
        }
        provider = MemoryProvider(config)

        assert provider.mode == "remote"
        assert provider.k == 3
        assert provider.max_tokens == 2000  # default

    def test_default_mode_is_remote(self):
        """Test default mode is remote for backward compatibility."""
        config = {"k": 3}
        provider = MemoryProvider(config)

        assert provider.mode == "remote"

    def test_default_k_and_max_tokens(self):
        """Test default k and max_tokens values."""
        config = {"mode": "local"}
        provider = MemoryProvider(config)

        assert provider.k == 3
        assert provider.max_tokens == 2000


class TestGetClientLazyInit:
    """Test lazy initialization of client."""

    @patch("app.ai.providers.memory.openmemory.openmemory.logger")
    def test_local_mode_client_init(self, mock_logger):
        """Test local mode client initialization."""
        config = {
            "mode": "local",
            "local_path": "./test.sqlite",
            "tier": "fast",
            "embeddings_provider": "synthetic",
        }
        provider = MemoryProvider(config)

        with patch(
            "app.ai.providers.memory.openmemory.openmemory.OpenMemory"
        ) as mock_om:
            mock_client = MagicMock()
            mock_om.return_value = mock_client

            client = provider._get_client()

            # Verify OpenMemory was called with correct args
            mock_om.assert_called_once_with(
                path="./test.sqlite", tier="fast", embeddings={"provider": "synthetic"}
            )
            assert client == mock_client
            assert provider._client_initialized is True

    @patch("app.ai.providers.memory.openmemory.openmemory.logger")
    def test_remote_mode_client_init(self, mock_logger):
        """Test remote mode client initialization."""
        config = {
            "mode": "remote",
            "base_url": "http://test:8080",
            "api_key": "test-key",
        }
        provider = MemoryProvider(config)

        with patch(
            "app.ai.providers.memory.openmemory.openmemory.OpenMemory"
        ) as mock_om:
            mock_client = MagicMock()
            mock_om.return_value = mock_client

            client = provider._get_client()

            # Verify OpenMemory was called with correct args
            mock_om.assert_called_once_with(
                mode="remote", url="http://test:8080", api_key="test-key"
            )
            assert client == mock_client

    def test_missing_openmemory_package(self):
        """Test error when openmemory-py is not installed."""
        config = {"mode": "local"}
        provider = MemoryProvider(config)

        with patch(
            "builtins.__import__",
            side_effect=ImportError("No module named 'openmemory'"),
        ):
            with pytest.raises(ImportError) as exc_info:
                provider._get_client()

            assert "openmemory-py" in str(exc_info.value)
            assert "pip install" in str(exc_info.value)

    @patch("app.ai.providers.memory.openmemory.openmemory.logger")
    def test_client_cached_after_init(self, mock_logger):
        """Test client is cached after first initialization."""
        config = {"mode": "local", "embeddings_provider": "synthetic"}
        provider = MemoryProvider(config)

        with patch(
            "app.ai.providers.memory.openmemory.openmemory.OpenMemory"
        ) as mock_om:
            mock_client = MagicMock()
            mock_om.return_value = mock_client

            client1 = provider._get_client()
            client2 = provider._get_client()

            # Should only init once
            assert mock_om.call_count == 1
            assert client1 == client2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
