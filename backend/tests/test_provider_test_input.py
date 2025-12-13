"""
Unit tests for Provider Test Input/Output schemas and testing functionality.

Tests for:
- ProviderTestInput validation
- ProviderTestOutput structure
- ASR with audio_base64 input
- TTS with custom text input
- Backward compatibility (no input_data)
"""

import base64
import pytest
from pydantic import ValidationError

from src.app.schemas.provider import (
    ProviderTestInput,
    ProviderTestOutput,
    ProviderTestRequest,
    ProviderTestByReferenceRequest,
    ProviderTestResult,
    ProviderCategory,
)


class TestProviderTestInputSchema:
    """Tests for ProviderTestInput validation."""

    def test_empty_input_data(self):
        """Test that empty input_data is valid (all fields optional)."""
        input_data = ProviderTestInput()
        assert input_data.audio_base64 is None
        assert input_data.audio_format is None
        assert input_data.text is None
        assert input_data.prompt is None
        assert input_data.image_base64 is None
        assert input_data.question is None

    def test_asr_input_with_audio_base64(self):
        """Test ASR input with audio_base64."""
        # Create a minimal valid base64 audio (fake data for testing schema)
        fake_audio = base64.b64encode(b"RIFF" + b"\x00" * 100).decode("utf-8")

        input_data = ProviderTestInput(
            audio_base64=fake_audio,
            audio_format="wav",
        )
        assert input_data.audio_base64 == fake_audio
        assert input_data.audio_format == "wav"

    def test_tts_input_with_text(self):
        """Test TTS input with custom text."""
        input_data = ProviderTestInput(text="Xin chào thế giới")
        assert input_data.text == "Xin chào thế giới"

    def test_llm_input_with_prompt(self):
        """Test LLM input with custom prompt."""
        input_data = ProviderTestInput(prompt="Tell me a joke")
        assert input_data.prompt == "Tell me a joke"

    def test_vllm_input_with_image_and_question(self):
        """Test VLLM input with image_base64 and question."""
        fake_image = base64.b64encode(b"\xff\xd8\xff" + b"\x00" * 100).decode("utf-8")

        input_data = ProviderTestInput(
            image_base64=fake_image,
            question="What is in this image?",
        )
        assert input_data.image_base64 == fake_image
        assert input_data.question == "What is in this image?"

    def test_text_max_length_validation(self):
        """Test that text field respects max_length."""
        long_text = "a" * 1001  # max is 1000

        with pytest.raises(ValidationError) as exc_info:
            ProviderTestInput(text=long_text)

        assert "text" in str(exc_info.value)

    def test_prompt_max_length_validation(self):
        """Test that prompt field respects max_length."""
        long_prompt = "a" * 2001  # max is 2000

        with pytest.raises(ValidationError) as exc_info:
            ProviderTestInput(prompt=long_prompt)

        assert "prompt" in str(exc_info.value)

    def test_question_max_length_validation(self):
        """Test that question field respects max_length."""
        long_question = "a" * 1001  # max is 1000

        with pytest.raises(ValidationError) as exc_info:
            ProviderTestInput(question=long_question)

        assert "question" in str(exc_info.value)

    def test_audio_base64_max_length_validation(self):
        """Test that audio_base64 field respects max_length (~10MB)."""
        # 14_000_000 is the max length for base64 (roughly 10MB binary)
        long_audio = "a" * 14_000_001

        with pytest.raises(ValidationError) as exc_info:
            ProviderTestInput(audio_base64=long_audio)

        assert "audio_base64" in str(exc_info.value)


class TestProviderTestOutputSchema:
    """Tests for ProviderTestOutput structure."""

    def test_empty_output(self):
        """Test that empty output is valid."""
        output = ProviderTestOutput()
        assert output.text is None
        assert output.audio_base64 is None
        assert output.audio_format is None
        assert output.audio_size_bytes is None
        assert output.metadata is None

    def test_text_output_for_llm(self):
        """Test text output (LLM response)."""
        output = ProviderTestOutput(text="Hello! How can I help you?")
        assert output.text == "Hello! How can I help you?"
        assert output.audio_base64 is None

    def test_text_output_for_asr(self):
        """Test text output (ASR transcription)."""
        output = ProviderTestOutput(text="Đây là văn bản được nhận dạng")
        assert output.text == "Đây là văn bản được nhận dạng"

    def test_audio_output_for_tts(self):
        """Test audio output (TTS)."""
        fake_audio = base64.b64encode(b"audio_data").decode("utf-8")
        output = ProviderTestOutput(
            audio_base64=fake_audio,
            audio_format="wav",
            audio_size_bytes=12345,
        )
        assert output.audio_base64 == fake_audio
        assert output.audio_format == "wav"
        assert output.audio_size_bytes == 12345

    def test_metadata_output(self):
        """Test metadata field."""
        output = ProviderTestOutput(
            metadata={"type": "nomem", "note": "No memory storage"}
        )
        assert output.metadata["type"] == "nomem"
        assert output.metadata["note"] == "No memory storage"


class TestProviderTestRequestSchema:
    """Tests for ProviderTestRequest with input_data."""

    def test_request_without_input_data(self):
        """Test backward compatibility - request without input_data."""
        request = ProviderTestRequest(
            category=ProviderCategory.LLM,
            type="openai",
            config={"model_name": "gpt-4", "api_key": "sk-xxx"},
        )
        assert request.input_data is None

    def test_request_with_null_input_data(self):
        """Test request with explicit null input_data."""
        request = ProviderTestRequest(
            category=ProviderCategory.LLM,
            type="openai",
            config={"model_name": "gpt-4", "api_key": "sk-xxx"},
            input_data=None,
        )
        assert request.input_data is None

    def test_request_with_asr_input(self):
        """Test ASR request with audio_base64."""
        fake_audio = base64.b64encode(b"test_audio").decode("utf-8")
        request = ProviderTestRequest(
            category=ProviderCategory.ASR,
            type="deepgram",
            config={"api_key": "xxx"},
            input_data=ProviderTestInput(
                audio_base64=fake_audio,
                audio_format="wav",
            ),
        )
        assert request.input_data is not None
        assert request.input_data.audio_base64 == fake_audio
        assert request.input_data.audio_format == "wav"

    def test_request_with_tts_input(self):
        """Test TTS request with custom text."""
        request = ProviderTestRequest(
            category=ProviderCategory.TTS,
            type="edge",
            config={"voice": "vi-VN-HoaiMyNeural"},
            input_data=ProviderTestInput(text="Custom text to synthesize"),
        )
        assert request.input_data is not None
        assert request.input_data.text == "Custom text to synthesize"

    def test_request_with_llm_input(self):
        """Test LLM request with custom prompt."""
        request = ProviderTestRequest(
            category=ProviderCategory.LLM,
            type="openai",
            config={"model_name": "gpt-4", "api_key": "sk-xxx"},
            input_data=ProviderTestInput(prompt="Custom prompt"),
        )
        assert request.input_data is not None
        assert request.input_data.prompt == "Custom prompt"


class TestProviderTestByReferenceRequestSchema:
    """Tests for ProviderTestByReferenceRequest with input_data."""

    def test_reference_request_without_input_data(self):
        """Test reference request without input_data."""
        request = ProviderTestByReferenceRequest(reference="config:CopilotLLM")
        assert request.reference == "config:CopilotLLM"
        assert request.input_data is None

    def test_reference_request_with_input_data(self):
        """Test reference request with input_data."""
        request = ProviderTestByReferenceRequest(
            reference="db:some-uuid",
            input_data=ProviderTestInput(text="Test text"),
        )
        assert request.reference == "db:some-uuid"
        assert request.input_data is not None
        assert request.input_data.text == "Test text"


class TestProviderTestResultSchema:
    """Tests for ProviderTestResult with output field."""

    def test_success_result_with_text_output(self):
        """Test success result with text output (LLM/ASR)."""
        result = ProviderTestResult(
            success=True,
            message="Provider hoạt động bình thường",
            latency_ms=523,
            output=ProviderTestOutput(text="Response text"),
        )
        assert result.success is True
        assert result.output is not None
        assert result.output.text == "Response text"
        assert result.error is None

    def test_success_result_with_audio_output(self):
        """Test success result with audio output (TTS)."""
        fake_audio = base64.b64encode(b"audio_bytes").decode("utf-8")
        result = ProviderTestResult(
            success=True,
            message="TTS provider hoạt động bình thường",
            latency_ms=456,
            output=ProviderTestOutput(
                audio_base64=fake_audio,
                audio_format="wav",
                audio_size_bytes=1000,
            ),
        )
        assert result.success is True
        assert result.output is not None
        assert result.output.audio_base64 == fake_audio
        assert result.output.audio_format == "wav"

    def test_failure_result(self):
        """Test failure result with error."""
        result = ProviderTestResult(
            success=False,
            error="API key không hợp lệ",
            error_code="AUTH_ERROR",
        )
        assert result.success is False
        assert result.error == "API key không hợp lệ"
        assert result.error_code == "AUTH_ERROR"
        assert result.output is None

    def test_result_backward_compatibility_no_output(self):
        """Test result without output field (backward compat)."""
        result = ProviderTestResult(
            success=True,
            message="OK",
            latency_ms=100,
        )
        assert result.success is True
        assert result.output is None


class TestProviderTesterFunctions:
    """Tests for provider_tester utility functions."""

    def test_decode_audio_base64_valid(self):
        """Test decoding valid audio base64."""
        from src.app.ai.providers.provider_tester import _decode_audio_base64

        # Create valid audio-like data (> 100 bytes)
        audio_data = b"RIFF" + b"\x00" * 200
        audio_base64 = base64.b64encode(audio_data).decode("utf-8")

        decoded, error = _decode_audio_base64(audio_base64)
        assert decoded is not None
        assert error is None
        assert decoded == audio_data

    def test_decode_audio_base64_too_small(self):
        """Test decoding audio that's too small."""
        from src.app.ai.providers.provider_tester import _decode_audio_base64

        small_data = b"abc"  # < 100 bytes
        audio_base64 = base64.b64encode(small_data).decode("utf-8")

        decoded, error = _decode_audio_base64(audio_base64)
        assert decoded is None
        assert error == "Audio data too small"

    def test_decode_audio_base64_invalid_encoding(self):
        """Test decoding invalid base64."""
        from src.app.ai.providers.provider_tester import _decode_audio_base64

        invalid_base64 = "not-valid-base64!!!"

        decoded, error = _decode_audio_base64(invalid_base64)
        assert decoded is None
        assert "Invalid base64 encoding" in error

    def test_detect_audio_format_wav(self):
        """Test detecting WAV format."""
        from src.app.ai.providers.provider_tester import _detect_audio_format

        wav_header = b"RIFF" + b"\x00" * 4 + b"WAVE" + b"\x00" * 100
        assert _detect_audio_format(wav_header) == "wav"

    def test_detect_audio_format_mp3(self):
        """Test detecting MP3 format."""
        from src.app.ai.providers.provider_tester import _detect_audio_format

        mp3_header = b"ID3" + b"\x00" * 100
        assert _detect_audio_format(mp3_header) == "mp3"

    def test_detect_audio_format_ogg(self):
        """Test detecting OGG format."""
        from src.app.ai.providers.provider_tester import _detect_audio_format

        ogg_header = b"OggS" + b"\x00" * 100
        assert _detect_audio_format(ogg_header) == "ogg"

    def test_detect_audio_format_unknown_defaults_wav(self):
        """Test that unknown format defaults to wav."""
        from src.app.ai.providers.provider_tester import _detect_audio_format

        unknown_data = b"\x00" * 100
        assert _detect_audio_format(unknown_data) == "wav"
