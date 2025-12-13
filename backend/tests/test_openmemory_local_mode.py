"""
Test script for OpenMemory provider local mode validation.
Run this manually to verify Phase 3 validation requirements.
"""

import asyncio
import json
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from app.ai.providers.schema_registry import get_provider_schema
from app.ai.providers.memory.openmemory.openmemory import MemoryProvider


def test_schema_has_mode_field():
    """Verify schema includes mode field."""
    schema = get_provider_schema("Memory", "openmemory")
    assert schema is not None, "Schema not found"

    mode_field = next((f for f in schema.fields if f.name == "mode"), None)
    assert mode_field is not None, "mode field not found"
    assert mode_field.type == "select", "mode should be SELECT type"
    assert mode_field.required is True, "mode should be required"
    assert mode_field.default == "remote", "mode default should be 'remote'"
    print("✓ Schema has mode field with correct config")


def test_schema_has_local_fields():
    """Verify schema includes local mode fields."""
    schema = get_provider_schema("Memory", "openmemory")

    local_fields = [
        "local_path",
        "tier",
        "embeddings_provider",
        "embeddings_api_key",
        "embeddings_model",
    ]
    for field_name in local_fields:
        field = next((f for f in schema.fields if f.name == field_name), None)
        assert field is not None, f"{field_name} field not found"
        assert (
            "[Local mode]" in field.description
        ), f"{field_name} should have [Local mode] prefix"
    print("✓ Schema has all local mode fields")


def test_schema_has_remote_fields():
    """Verify schema includes remote mode fields."""
    schema = get_provider_schema("Memory", "openmemory")

    remote_fields = ["base_url", "api_key"]
    for field_name in remote_fields:
        field = next((f for f in schema.fields if f.name == field_name), None)
        assert field is not None, f"{field_name} field not found"
        assert (
            "[Remote mode]" in field.description
        ), f"{field_name} should have [Remote mode] prefix"
    print("✓ Schema has all remote mode fields")


def test_local_mode_synthetic_config():
    """Test local mode with synthetic embeddings."""
    config = {
        "mode": "local",
        "local_path": "./test_memory.sqlite",
        "tier": "fast",
        "embeddings_provider": "synthetic",
        "k": 5,
        "max_tokens": 2000,
    }

    provider = MemoryProvider(config)
    assert provider.mode == "local"
    assert provider.k == 5

    # Test _build_embeddings_config
    embeddings_config = provider._build_embeddings_config()
    assert embeddings_config == {"provider": "synthetic"}
    print("✓ Local mode with synthetic embeddings config works")


def test_local_mode_openai_config():
    """Test local mode with OpenAI embeddings."""
    config = {
        "mode": "local",
        "local_path": "./test_memory.sqlite",
        "tier": "quality",
        "embeddings_provider": "openai",
        "embeddings_api_key": "sk-test123",
        "embeddings_model": "text-embedding-3-small",
        "k": 3,
    }

    provider = MemoryProvider(config)
    embeddings_config = provider._build_embeddings_config()

    assert embeddings_config["provider"] == "openai"
    assert embeddings_config["apiKey"] == "sk-test123"
    assert embeddings_config["model"] == "text-embedding-3-small"
    print("✓ Local mode with OpenAI embeddings config works")


def test_local_mode_gemini_config():
    """Test local mode with Gemini embeddings."""
    config = {
        "mode": "local",
        "local_path": "./test_memory.sqlite",
        "tier": "balanced",
        "embeddings_provider": "gemini",
        "embeddings_api_key": "AIza-test",
        "k": 3,
    }

    provider = MemoryProvider(config)
    embeddings_config = provider._build_embeddings_config()

    assert embeddings_config["provider"] == "gemini"
    assert embeddings_config["apiKey"] == "AIza-test"
    assert "model" not in embeddings_config  # No model specified
    print("✓ Local mode with Gemini embeddings config works")


def test_remote_mode_backward_compatibility():
    """Test remote mode still works (backward compatibility)."""
    config = {
        "mode": "remote",
        "base_url": "http://localhost:8080",
        "api_key": "test-key",
        "k": 3,
        "max_tokens": 2000,
    }

    provider = MemoryProvider(config)
    assert provider.mode == "remote"
    assert provider.k == 3
    print("✓ Remote mode backward compatibility works")


def test_default_mode_is_remote():
    """Test that default mode is remote for backward compatibility."""
    config = {
        "base_url": "http://localhost:8080",
        "k": 3,
    }

    provider = MemoryProvider(config)
    assert provider.mode == "remote"
    print("✓ Default mode is 'remote'")


if __name__ == "__main__":
    print("=" * 60)
    print("OpenMemory Provider Local Mode - Validation Tests")
    print("=" * 60)

    tests = [
        test_schema_has_mode_field,
        test_schema_has_local_fields,
        test_schema_has_remote_fields,
        test_local_mode_synthetic_config,
        test_local_mode_openai_config,
        test_local_mode_gemini_config,
        test_remote_mode_backward_compatibility,
        test_default_mode_is_remote,
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
            failed += 1

    print("=" * 60)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 60)

    sys.exit(0 if failed == 0 else 1)
