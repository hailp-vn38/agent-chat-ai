"""
Standalone unit tests for OpenMemory provider local mode.
Run without pytest infrastructure to avoid dependency issues.
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from app.ai.providers.memory.openmemory.openmemory import MemoryProvider


def test_build_embeddings_config_synthetic():
    """Test synthetic embeddings config."""
    config = {"mode": "local", "embeddings_provider": "synthetic"}
    provider = MemoryProvider(config)
    result = provider._build_embeddings_config()
    assert result == {
        "provider": "synthetic"
    }, f"Expected synthetic config, got {result}"
    print("✓ test_build_embeddings_config_synthetic")


def test_build_embeddings_config_openai_with_model():
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
    print("✓ test_build_embeddings_config_openai_with_model")


def test_build_embeddings_config_openai_without_model():
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
    print("✓ test_build_embeddings_config_openai_without_model")


def test_build_embeddings_config_gemini():
    """Test Gemini embeddings config."""
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
    print("✓ test_build_embeddings_config_gemini")


def test_local_mode_initialization():
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
    print("✓ test_local_mode_initialization")


def test_remote_mode_initialization():
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
    print("✓ test_remote_mode_initialization")


def test_default_mode_is_remote():
    """Test default mode is remote for backward compatibility."""
    config = {"k": 3}
    provider = MemoryProvider(config)

    assert provider.mode == "remote"
    print("✓ test_default_mode_is_remote")


def test_default_k_and_max_tokens():
    """Test default k and max_tokens values."""
    config = {"mode": "local"}
    provider = MemoryProvider(config)

    assert provider.k == 3
    assert provider.max_tokens == 2000
    print("✓ test_default_k_and_max_tokens")


def test_local_mode_client_init():
    """Test local mode client initialization."""
    config = {
        "mode": "local",
        "local_path": "./test.sqlite",
        "tier": "fast",
        "embeddings_provider": "synthetic",
    }
    provider = MemoryProvider(config)

    with patch("app.ai.providers.memory.openmemory.openmemory.OpenMemory") as mock_om:
        mock_client = MagicMock()
        mock_om.return_value = mock_client

        client = provider._get_client()

        # Verify OpenMemory was called with correct args
        call_args = mock_om.call_args
        assert call_args[1]["path"] == "./test.sqlite"
        assert call_args[1]["tier"] == "fast"
        assert call_args[1]["embeddings"] == {"provider": "synthetic"}
        assert client == mock_client
        assert provider._client_initialized is True
    print("✓ test_local_mode_client_init")


def test_remote_mode_client_init():
    """Test remote mode client initialization."""
    config = {
        "mode": "remote",
        "base_url": "http://test:8080",
        "api_key": "test-key",
    }
    provider = MemoryProvider(config)

    with patch("app.ai.providers.memory.openmemory.openmemory.OpenMemory") as mock_om:
        mock_client = MagicMock()
        mock_om.return_value = mock_client

        client = provider._get_client()

        # Verify OpenMemory was called with correct args
        call_args = mock_om.call_args
        assert call_args[1]["mode"] == "remote"
        assert call_args[1]["url"] == "http://test:8080"
        assert call_args[1]["api_key"] == "test-key"
        assert client == mock_client
    print("✓ test_remote_mode_client_init")


def test_client_cached_after_init():
    """Test client is cached after first initialization."""
    config = {"mode": "local", "embeddings_provider": "synthetic"}
    provider = MemoryProvider(config)

    with patch("app.ai.providers.memory.openmemory.openmemory.OpenMemory") as mock_om:
        mock_client = MagicMock()
        mock_om.return_value = mock_client

        client1 = provider._get_client()
        client2 = provider._get_client()

        # Should only init once
        assert mock_om.call_count == 1
        assert client1 == client2
    print("✓ test_client_cached_after_init")


if __name__ == "__main__":
    print("=" * 60)
    print("OpenMemory Provider - Unit Tests")
    print("=" * 60)

    tests = [
        test_build_embeddings_config_synthetic,
        test_build_embeddings_config_openai_with_model,
        test_build_embeddings_config_openai_without_model,
        test_build_embeddings_config_gemini,
        test_local_mode_initialization,
        test_remote_mode_initialization,
        test_default_mode_is_remote,
        test_default_k_and_max_tokens,
        test_local_mode_client_init,
        test_remote_mode_client_init,
        test_client_cached_after_init,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            test()
            passed += 1
        except AssertionError as e:
            print(f"✗ {test.__name__}: {e}")
            failed += 1
        except Exception as e:
            print(f"✗ {test.__name__}: Unexpected error: {e}")
            import traceback

            traceback.print_exc()
            failed += 1

    print("=" * 60)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 60)

    sys.exit(0 if failed == 0 else 1)
