"""
Unit tests for Provider Schema Validator.
"""

import pytest

from src.app.ai.providers.schema_validator import validate_provider_config
from src.app.ai.providers.schema_registry import (
    get_provider_schema,
    get_all_schemas,
    list_categories,
    list_provider_types,
)


class TestSchemaRegistry:
    """Tests for schema registry functions."""

    def test_list_categories(self):
        """Test that all expected categories are available."""
        categories = list_categories()
        assert "LLM" in categories
        assert "TTS" in categories
        assert "ASR" in categories

    def test_list_provider_types_llm(self):
        """Test LLM provider types."""
        types = list_provider_types("LLM")
        assert "openai" in types
        assert "gemini" in types

    def test_list_provider_types_tts(self):
        """Test TTS provider types."""
        types = list_provider_types("TTS")
        assert "edge" in types
        assert "google" in types
        assert "deepgram" in types

    def test_list_provider_types_asr(self):
        """Test ASR provider types."""
        types = list_provider_types("ASR")
        assert "openai" in types
        assert "deepgram" in types
        assert "sherpa_onnx_local" in types

    def test_list_provider_types_invalid_category(self):
        """Test with invalid category returns empty list."""
        types = list_provider_types("INVALID")
        assert types == []

    def test_get_provider_schema(self):
        """Test getting a specific provider schema."""
        schema = get_provider_schema("LLM", "openai")
        assert schema is not None
        assert schema.label == "OpenAI Compatible"
        assert len(schema.fields) > 0

    def test_get_provider_schema_invalid(self):
        """Test getting invalid provider schema returns None."""
        schema = get_provider_schema("LLM", "invalid_provider")
        assert schema is None

    def test_get_all_schemas(self):
        """Test getting all schemas."""
        schemas = get_all_schemas()
        assert "LLM" in schemas
        assert "TTS" in schemas
        assert "ASR" in schemas
        assert "openai" in schemas["LLM"]


class TestValidateProviderConfig:
    """Tests for validate_provider_config function."""

    # ========== LLM OpenAI Tests ==========

    def test_llm_openai_valid_minimal(self):
        """Test valid minimal OpenAI config."""
        config = {
            "model_name": "gpt-4",
            "api_key": "sk-test-key",
        }
        is_valid, normalized, errors = validate_provider_config("LLM", "openai", config)

        assert is_valid is True
        assert len(errors) == 0
        assert normalized["type"] == "openai"
        assert normalized["model_name"] == "gpt-4"
        assert normalized["api_key"] == "sk-test-key"
        # Check defaults applied
        assert normalized["temperature"] == 0.7
        assert normalized["max_tokens"] == 4000

    def test_llm_openai_valid_full(self):
        """Test valid full OpenAI config."""
        config = {
            "model_name": "gpt-4.1",
            "api_key": "sk-test-key",
            "base_url": "https://api.example.com/v1",
            "temperature": 0.5,
            "max_tokens": 2000,
            "top_p": 0.9,
            "frequency_penalty": 0.5,
            "timeout": 120,
        }
        is_valid, normalized, errors = validate_provider_config("LLM", "openai", config)

        assert is_valid is True
        assert normalized["temperature"] == 0.5
        assert normalized["max_tokens"] == 2000
        assert normalized["base_url"] == "https://api.example.com/v1"

    def test_llm_openai_missing_required(self):
        """Test OpenAI config missing required fields."""
        config = {
            "temperature": 0.7,
        }
        is_valid, normalized, errors = validate_provider_config("LLM", "openai", config)

        assert is_valid is False
        assert "Field 'model_name' is required" in errors
        assert "Field 'api_key' is required" in errors

    def test_llm_openai_invalid_temperature(self):
        """Test OpenAI config with invalid temperature."""
        config = {
            "model_name": "gpt-4",
            "api_key": "sk-test-key",
            "temperature": 3.0,  # max is 2
        }
        is_valid, normalized, errors = validate_provider_config("LLM", "openai", config)

        assert is_valid is False
        assert any("temperature" in e and "<=" in e for e in errors)

    def test_llm_openai_invalid_max_tokens(self):
        """Test OpenAI config with invalid max_tokens."""
        config = {
            "model_name": "gpt-4",
            "api_key": "sk-test-key",
            "max_tokens": 0,  # min is 1
        }
        is_valid, normalized, errors = validate_provider_config("LLM", "openai", config)

        assert is_valid is False
        assert any("max_tokens" in e for e in errors)

    # ========== LLM Gemini Tests ==========

    def test_llm_gemini_valid(self):
        """Test valid Gemini config."""
        config = {
            "api_key": "test-api-key",
            "model_name": "gemini-2.0-flash",
        }
        is_valid, normalized, errors = validate_provider_config("LLM", "gemini", config)

        assert is_valid is True
        assert normalized["type"] == "gemini"
        assert normalized["model_name"] == "gemini-2.0-flash"

    def test_llm_gemini_invalid_model(self):
        """Test Gemini config with invalid model selection."""
        config = {
            "api_key": "test-api-key",
            "model_name": "invalid-model",  # not in options
        }
        is_valid, normalized, errors = validate_provider_config("LLM", "gemini", config)

        assert is_valid is False
        assert any("model_name" in e for e in errors)

    # ========== TTS Edge Tests ==========

    def test_tts_edge_valid(self):
        """Test valid Edge TTS config."""
        config = {
            "voice": "vi-VN-HoaiMyNeural",
        }
        is_valid, normalized, errors = validate_provider_config("TTS", "edge", config)

        assert is_valid is True
        assert normalized["type"] == "edge"
        assert normalized["voice"] == "vi-VN-HoaiMyNeural"

    def test_tts_edge_missing_required(self):
        """Test Edge TTS missing required voice."""
        config = {}
        is_valid, normalized, errors = validate_provider_config("TTS", "edge", config)

        assert is_valid is False
        assert "Field 'voice' is required" in errors

    def test_tts_edge_invalid_voice(self):
        """Test Edge TTS with invalid voice."""
        config = {
            "voice": "invalid-voice",
        }
        is_valid, normalized, errors = validate_provider_config("TTS", "edge", config)

        assert is_valid is False
        assert any("voice" in e for e in errors)

    # ========== TTS Google Tests ==========

    def test_tts_google_valid(self):
        """Test valid Google TTS config."""
        config = {
            "api_key": "test-api-key",
            "voice_name": "vi-VN-Chirp3-HD-Aoede",
            "speaking_rate": 1.2,
        }
        is_valid, normalized, errors = validate_provider_config("TTS", "google", config)

        assert is_valid is True
        assert normalized["type"] == "google"
        assert normalized["speaking_rate"] == 1.2

    def test_tts_google_invalid_speaking_rate(self):
        """Test Google TTS with invalid speaking rate."""
        config = {
            "api_key": "test-api-key",
            "speaking_rate": 5.0,  # max is 4.0
        }
        is_valid, normalized, errors = validate_provider_config("TTS", "google", config)

        assert is_valid is False
        assert any("speaking_rate" in e for e in errors)

    # ========== ASR Tests ==========

    def test_asr_deepgram_valid(self):
        """Test valid Deepgram ASR config."""
        config = {
            "api_key": "test-api-key",
            "model": "nova-2",
            "language": "vi",
            "smart_format": True,
        }
        is_valid, normalized, errors = validate_provider_config("ASR", "deepgram", config)

        assert is_valid is True
        assert normalized["type"] == "deepgram"
        assert normalized["smart_format"] is True

    def test_asr_sherpa_onnx_valid(self):
        """Test valid Sherpa ONNX local ASR config."""
        config = {
            "repo_id": "hynt/Zipformer-30M-RNNT-6000h",
            "use_int8": True,
            "num_threads": 4,
            "decoding_method": "greedy_search",
        }
        is_valid, normalized, errors = validate_provider_config(
            "ASR", "sherpa_onnx_local", config
        )

        assert is_valid is True
        assert normalized["type"] == "sherpa_onnx_local"
        assert normalized["num_threads"] == 4

    def test_asr_sherpa_onnx_invalid_threads(self):
        """Test Sherpa ONNX with invalid num_threads."""
        config = {
            "num_threads": 20,  # max is 16
        }
        is_valid, normalized, errors = validate_provider_config(
            "ASR", "sherpa_onnx_local", config
        )

        assert is_valid is False
        assert any("num_threads" in e for e in errors)

    # ========== Invalid Provider Tests ==========

    def test_invalid_category(self):
        """Test with invalid category."""
        config = {"key": "value"}
        is_valid, normalized, errors = validate_provider_config(
            "INVALID", "openai", config
        )

        assert is_valid is False
        assert any("Unknown provider" in e for e in errors)

    def test_invalid_provider_type(self):
        """Test with invalid provider type."""
        config = {"key": "value"}
        is_valid, normalized, errors = validate_provider_config(
            "LLM", "invalid_type", config
        )

        assert is_valid is False
        assert any("Unknown provider" in e for e in errors)

    # ========== Type Coercion Tests ==========

    def test_string_to_number_coercion(self):
        """Test string values are coerced to numbers."""
        config = {
            "model_name": "gpt-4",
            "api_key": "sk-test",
            "temperature": "0.5",  # string
            "max_tokens": "2000",  # string
        }
        is_valid, normalized, errors = validate_provider_config("LLM", "openai", config)

        assert is_valid is True
        assert normalized["temperature"] == 0.5
        assert normalized["max_tokens"] == 2000

    def test_boolean_coercion(self):
        """Test boolean coercion from various types."""
        config = {
            "api_key": "test",
            "model": "nova-2",
            "language": "vi",
            "smart_format": "true",  # string
        }
        is_valid, normalized, errors = validate_provider_config("ASR", "deepgram", config)

        assert is_valid is True
        assert normalized["smart_format"] is True

        # Test with "false" string
        config["smart_format"] = "false"
        is_valid, normalized, errors = validate_provider_config("ASR", "deepgram", config)
        assert normalized["smart_format"] is False

        # Test with 1
        config["smart_format"] = 1
        is_valid, normalized, errors = validate_provider_config("ASR", "deepgram", config)
        assert normalized["smart_format"] is True

    def test_empty_string_treated_as_none(self):
        """Test empty strings are treated as None (use default)."""
        config = {
            "model_name": "gpt-4",
            "api_key": "sk-test",
            "base_url": "",  # empty string
        }
        is_valid, normalized, errors = validate_provider_config("LLM", "openai", config)

        assert is_valid is True
        # Empty string should use default
        assert normalized["base_url"] == "https://api.openai.com/v1"

