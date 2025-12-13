"""
Provider Tester - Test provider connections by making actual API calls.
"""

from __future__ import annotations

import base64
import time
from typing import Any

from app.core.logger import setup_logging
from app.schemas.provider import (
    ProviderTestInput,
    ProviderTestOutput,
    ProviderTestResult,
)

logger = setup_logging()
TAG = __name__


def _detect_audio_format(audio_bytes: bytes) -> str:
    """Detect audio format from magic bytes."""
    if audio_bytes[:4] == b"RIFF" and audio_bytes[8:12] == b"WAVE":
        return "wav"
    elif audio_bytes[:3] == b"ID3" or audio_bytes[:2] == b"\xff\xfb":
        return "mp3"
    elif audio_bytes[:4] == b"OggS":
        return "ogg"
    elif audio_bytes[:4] == b"\x1aE\xdf\xa3":  # EBML header (webm/mkv)
        return "webm"
    elif audio_bytes[4:8] == b"ftyp":  # MP4/M4A
        return "m4a"
    return "wav"  # default


def _convert_audio_to_pcm(
    audio_bytes: bytes, audio_format: str
) -> tuple[bytes | None, str | None]:
    """Convert audio to PCM 16kHz mono using ffmpeg.

    Args:
        audio_bytes: Raw audio data
        audio_format: Audio format hint (webm, ogg, mp3, etc.)

    Returns:
        Tuple of (pcm_bytes, error_message)
    """
    import subprocess
    import tempfile
    import os

    # WAV already in correct format - just validate
    if audio_format == "wav":
        # Kiểm tra xem WAV có đúng format 16kHz mono 16-bit không
        if audio_bytes[:4] == b"RIFF" and audio_bytes[8:12] == b"WAVE":
            return audio_bytes, None
        return None, "Invalid WAV file"

    # PCM raw data - wrap in WAV header
    if audio_format == "pcm":
        try:
            import wave
            import io

            wav_buffer = io.BytesIO()
            with wave.open(wav_buffer, "wb") as wav_file:
                wav_file.setnchannels(1)
                wav_file.setsampwidth(2)
                wav_file.setframerate(16000)
                wav_file.writeframes(audio_bytes)
            wav_buffer.seek(0)
            return wav_buffer.read(), None
        except Exception as e:
            return None, f"Failed to wrap PCM in WAV: {e}"

    # For other formats (webm, ogg, mp3, m4a), use ffmpeg to convert
    try:
        # Tạo temp files
        with tempfile.NamedTemporaryFile(
            suffix=f".{audio_format}", delete=False
        ) as input_file:
            input_file.write(audio_bytes)
            input_path = input_file.name

        output_path = input_path.rsplit(".", 1)[0] + ".wav"

        try:
            # Convert to WAV 16kHz mono 16-bit using ffmpeg
            result = subprocess.run(
                [
                    "ffmpeg",
                    "-y",  # Overwrite output
                    "-i",
                    input_path,
                    "-ar",
                    "16000",  # Sample rate 16kHz
                    "-ac",
                    "1",  # Mono
                    "-acodec",
                    "pcm_s16le",  # 16-bit PCM
                    "-f",
                    "wav",
                    output_path,
                ],
                capture_output=True,
                timeout=30,
            )

            if result.returncode != 0:
                error_msg = result.stderr.decode("utf-8", errors="replace")
                logger.bind(tag=TAG).error(f"ffmpeg error: {error_msg}")
                return None, f"Audio conversion failed: {error_msg[:200]}"

            # Read converted WAV
            with open(output_path, "rb") as f:
                wav_data = f.read()

            return wav_data, None

        finally:
            # Cleanup temp files
            if os.path.exists(input_path):
                os.remove(input_path)
            if os.path.exists(output_path):
                os.remove(output_path)

    except FileNotFoundError:
        return None, "ffmpeg not found. Please install ffmpeg to convert audio formats."
    except subprocess.TimeoutExpired:
        return None, "Audio conversion timeout (30s)"
    except Exception as e:
        logger.bind(tag=TAG).error(f"Audio conversion error: {e}")
        return None, f"Audio conversion error: {e}"


async def test_provider_connection(
    category: str,
    provider_type: str,
    config: dict[str, Any],
    input_data: ProviderTestInput | None = None,
) -> ProviderTestResult:
    """
    Test provider connection by creating instance and making minimal API call.

    Args:
        category: Provider category (LLM, TTS, ASR, VLLM, Memory)
        provider_type: Provider type (openai, gemini, edge, etc.)
        config: Normalized provider config
        input_data: Optional custom input data for testing

    Returns:
        ProviderTestResult with success status and structured output
    """
    if category == "LLM":
        return await test_llm_provider(config, input_data)
    elif category == "TTS":
        return await test_tts_provider(config, input_data)
    elif category == "ASR":
        return await test_asr_provider(config, input_data)
    elif category == "VLLM":
        return await test_vllm_provider(config, input_data)
    elif category == "Memory":
        return await test_memory_provider(config)
    else:
        return ProviderTestResult(
            success=True,
            message=f"Testing not implemented for category '{category}'",
        )


async def test_llm_provider(
    config: dict[str, Any],
    input_data: ProviderTestInput | None = None,
) -> ProviderTestResult:
    """
    Test LLM provider by sending a simple test prompt.

    Makes minimal API call to verify:
    - API key is valid
    - Model exists and is accessible
    - Connection to API endpoint works
    """
    try:
        from app.ai.module_factory import initialize_llm_from_config

        # Use custom prompt if provided, otherwise use default
        custom_prompt = input_data.prompt if input_data and input_data.prompt else None

        # Create instance
        start_time = time.time()
        llm_instance = initialize_llm_from_config(config)

        # Test with minimal prompt
        if custom_prompt:
            test_dialogue = [
                {"role": "user", "content": custom_prompt},
            ]
        else:
            test_dialogue = [
                {
                    "role": "system",
                    "content": "You are a test assistant. Reply with exactly 'OK'.",
                },
                {"role": "user", "content": "Test"},
            ]

        response = ""
        for chunk in llm_instance.response("test_session", test_dialogue):
            response += chunk
            # Stop after getting some response to minimize cost
            if len(response) >= 50:
                break

        latency_ms = int((time.time() - start_time) * 1000)

        if response:
            return ProviderTestResult(
                success=True,
                message="LLM provider hoạt động bình thường",
                latency_ms=latency_ms,
                output=ProviderTestOutput(text=response[:100]),
            )
        else:
            return ProviderTestResult(
                success=False,
                error="Không nhận được response từ LLM",
                error_code="NO_RESPONSE",
            )

    except Exception as e:
        error_str = str(e).lower()

        # Detect common error types
        if (
            "authentication" in error_str
            or "api key" in error_str
            or "401" in error_str
        ):
            return ProviderTestResult(
                success=False,
                error="API key không hợp lệ",
                error_code="AUTH_ERROR",
            )
        elif "connection" in error_str or "timeout" in error_str:
            return ProviderTestResult(
                success=False,
                error="Không thể kết nối tới API",
                error_code="CONNECTION_ERROR",
            )
        elif "model" in error_str and "not found" in error_str:
            return ProviderTestResult(
                success=False,
                error="Model không tồn tại hoặc không có quyền truy cập",
                error_code="MODEL_NOT_FOUND",
            )
        elif "rate limit" in error_str or "429" in error_str:
            return ProviderTestResult(
                success=False,
                error="Đã vượt quá rate limit của API",
                error_code="RATE_LIMIT",
            )
        else:
            logger.bind(tag=TAG).error(f"LLM test error: {e}")
            return ProviderTestResult(
                success=False,
                error=str(e),
                error_code="UNKNOWN_ERROR",
            )


async def test_tts_provider(
    config: dict[str, Any],
    input_data: ProviderTestInput | None = None,
) -> ProviderTestResult:
    """
    Test TTS provider by synthesizing a short text.

    Verifies:
    - API key is valid (if required)
    - Voice/model exists
    - Audio can be generated
    """
    try:
        from app.ai.module_factory import initialize_tts_from_config

        # Use custom text if provided, otherwise use default
        test_text = input_data.text if input_data and input_data.text else "Xin chào"

        # Create instance
        start_time = time.time()
        tts_instance = initialize_tts_from_config(config, delete_audio=True)

        audio_bytes = await tts_instance.text_to_speak(test_text, output_file=None)

        latency_ms = int((time.time() - start_time) * 1000)

        if audio_bytes and len(audio_bytes) > 100:
            audio_format = _detect_audio_format(audio_bytes)
            audio_base64 = base64.b64encode(audio_bytes).decode("utf-8")
            return ProviderTestResult(
                success=True,
                message="TTS provider hoạt động bình thường",
                latency_ms=latency_ms,
                output=ProviderTestOutput(
                    audio_base64=audio_base64,
                    audio_format=audio_format,
                    audio_size_bytes=len(audio_bytes),
                ),
            )
        else:
            return ProviderTestResult(
                success=False,
                error="Không nhận được audio từ TTS",
                error_code="NO_OUTPUT",
            )

    except Exception as e:
        error_str = str(e).lower()

        if (
            "authentication" in error_str
            or "api key" in error_str
            or "401" in error_str
        ):
            return ProviderTestResult(
                success=False,
                error="API key không hợp lệ",
                error_code="AUTH_ERROR",
            )
        elif "voice" in error_str and (
            "not found" in error_str or "invalid" in error_str
        ):
            return ProviderTestResult(
                success=False,
                error="Voice không tồn tại",
                error_code="VOICE_NOT_FOUND",
            )
        elif "connection" in error_str or "timeout" in error_str:
            return ProviderTestResult(
                success=False,
                error="Không thể kết nối tới API",
                error_code="CONNECTION_ERROR",
            )
        else:
            logger.bind(tag=TAG).error(f"TTS test error: {e}")
            return ProviderTestResult(
                success=False,
                error=str(e),
                error_code="UNKNOWN_ERROR",
            )


def _get_test_audio_file() -> bytes | None:
    """Load test audio file từ src/app/config/audio-test/audio.wav"""
    import os

    script_dir = os.path.dirname(os.path.abspath(__file__))
    audio_path = os.path.join(
        script_dir, "..", "..", "config", "audio-test", "audio.wav"
    )
    audio_path = os.path.abspath(audio_path)

    if os.path.exists(audio_path):
        with open(audio_path, "rb") as f:
            return f.read()
    return None


def _decode_audio_base64(audio_base64: str) -> tuple[bytes | None, str | None]:
    """Decode base64 audio and validate.

    Returns:
        Tuple of (audio_bytes, error_message)
    """
    try:
        audio_bytes = base64.b64decode(audio_base64)
        # Check minimum size (valid audio should be > 100 bytes)
        if len(audio_bytes) < 100:
            return None, "Audio data too small"
        # Check max size (10MB)
        if len(audio_bytes) > 10 * 1024 * 1024:
            return None, "Audio data too large (max 10MB)"
        return audio_bytes, None
    except Exception as e:
        return None, f"Invalid base64 encoding: {e}"


async def test_asr_provider(
    config: dict[str, Any],
    input_data: ProviderTestInput | None = None,
) -> ProviderTestResult:
    """
    Test ASR provider bằng cách gửi audio thực tế.

    Verifies:
    - API key hợp lệ (nếu cần)
    - Model ASR tồn tại
    - Có thể nhận dạng giọng nói

    Notes:
    - Audio từ input_data sẽ được convert sang WAV 16kHz mono nếu cần
    - Hỗ trợ: wav, pcm, webm, ogg, mp3, m4a (cần ffmpeg)
    """
    import os
    import tempfile
    import wave
    import numpy as np

    try:
        from app.ai.module_factory import initialize_asr_from_config

        # Get audio data - from input or default file
        audio_data: bytes | None = None
        audio_format_hint: str | None = None
        is_user_audio = False  # Flag để biết có phải audio từ user không

        if input_data and input_data.audio_base64:
            audio_data, error = _decode_audio_base64(input_data.audio_base64)
            if error:
                return ProviderTestResult(
                    success=False,
                    error=error,
                    error_code="INVALID_AUDIO_FORMAT",
                )
            audio_format_hint = input_data.audio_format
            is_user_audio = True
        else:
            # Load default test audio file (already in WAV format)
            audio_data = _get_test_audio_file()
            if not audio_data:
                return ProviderTestResult(
                    success=False,
                    error="Không tìm thấy file audio test tại src/app/config/audio-test/audio.wav",
                    error_code="TEST_FILE_NOT_FOUND",
                )
            audio_format_hint = "wav"

        # Detect format if not provided
        if not audio_format_hint:
            audio_format_hint = _detect_audio_format(audio_data)

        # Convert audio to WAV 16kHz mono if needed (for user-uploaded audio)
        # Default test file is already in correct format
        if is_user_audio and audio_format_hint not in ("wav",):
            logger.bind(tag=TAG).info(
                f"Converting {audio_format_hint} audio to WAV 16kHz mono..."
            )
            wav_data, convert_error = _convert_audio_to_pcm(
                audio_data, audio_format_hint
            )
            if convert_error:
                return ProviderTestResult(
                    success=False,
                    error=f"Lỗi convert audio: {convert_error}",
                    error_code="AUDIO_CONVERSION_ERROR",
                )
            audio_data = wav_data
            audio_format_hint = "wav"
            logger.bind(tag=TAG).info(
                f"Audio converted successfully, size: {len(audio_data)} bytes"
            )

        # Create instance
        start_time = time.time()
        asr_instance = initialize_asr_from_config(config, delete_audio=True)

        if not asr_instance:
            return ProviderTestResult(
                success=False,
                error="Không thể khởi tạo ASR instance",
                error_code="INIT_ERROR",
            )

        # Lưu WAV data vào temp file và dùng trực tiếp
        # Vì speech_to_text mong đợi PCM chunks, ta cần extract PCM từ WAV
        try:
            import io

            wav_buffer = io.BytesIO(audio_data)
            with wave.open(wav_buffer, "rb") as wav_file:
                # Kiểm tra format
                if wav_file.getnchannels() != 1:
                    return ProviderTestResult(
                        success=False,
                        error=f"Audio phải là mono, nhận được {wav_file.getnchannels()} channels",
                        error_code="INVALID_AUDIO_FORMAT",
                    )
                if wav_file.getsampwidth() != 2:
                    return ProviderTestResult(
                        success=False,
                        error=f"Audio phải là 16-bit, nhận được {wav_file.getsampwidth() * 8}-bit",
                        error_code="INVALID_AUDIO_FORMAT",
                    )

                # Extract PCM frames
                pcm_data = wav_file.readframes(wav_file.getnframes())
        except Exception as e:
            return ProviderTestResult(
                success=False,
                error=f"Không thể đọc WAV file: {e}",
                error_code="INVALID_AUDIO_FORMAT",
            )

        # Test speech to text với PCM data
        asr_instance.audio_format = "pcm"
        text, _ = await asr_instance.speech_to_text([pcm_data], "test_session", "pcm")

        latency_ms = int((time.time() - start_time) * 1000)

        if text:
            return ProviderTestResult(
                success=True,
                message="ASR provider hoạt động bình thường",
                latency_ms=latency_ms,
                output=ProviderTestOutput(
                    text=text[:200] if len(text) > 200 else text,
                ),
            )
        else:
            return ProviderTestResult(
                success=False,
                error="Không nhận được kết quả nhận dạng từ ASR",
                error_code="NO_OUTPUT",
            )

    except Exception as e:
        error_str = str(e).lower()

        if (
            "authentication" in error_str
            or "api key" in error_str
            or "401" in error_str
        ):
            return ProviderTestResult(
                success=False,
                error="API key không hợp lệ",
                error_code="AUTH_ERROR",
            )
        elif "model" in error_str and "not found" in error_str:
            return ProviderTestResult(
                success=False,
                error="Model ASR không tồn tại",
                error_code="MODEL_NOT_FOUND",
            )
        elif "connection" in error_str or "timeout" in error_str:
            return ProviderTestResult(
                success=False,
                error="Không thể kết nối tới API",
                error_code="CONNECTION_ERROR",
            )
        elif "502" in error_str or "bad gateway" in error_str:
            return ProviderTestResult(
                success=False,
                error="Lỗi 502 Bad Gateway từ server",
                error_code="SERVER_ERROR",
            )
        else:
            logger.bind(tag=TAG).error(f"ASR test error: {e}")
            return ProviderTestResult(
                success=False,
                error=str(e),
                error_code="UNKNOWN_ERROR",
            )


def _get_test_image_base64() -> str | None:
    """Load test image from src/app/config/assets/images/image-test.jpg"""
    import os

    script_dir = os.path.dirname(os.path.abspath(__file__))
    image_path = os.path.join(
        script_dir, "..", "..", "config", "assets", "images", "image-test.jpg"
    )
    image_path = os.path.abspath(image_path)

    if os.path.exists(image_path):
        with open(image_path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")
    return None


async def test_vllm_provider(
    config: dict[str, Any],
    input_data: ProviderTestInput | None = None,
) -> ProviderTestResult:
    """
    Test VLLM (Vision LLM) provider by sending image + question.

    Verifies:
    - API key is valid
    - Model can process images
    - Response is generated
    """
    try:
        from app.ai.utils import vllm

        vllm_type = config.get("type")
        if not vllm_type:
            return ProviderTestResult(
                success=False,
                error="Config thiếu field 'type'",
                error_code="INVALID_CONFIG",
            )

        # Get image - from input or default file
        if input_data and input_data.image_base64:
            test_image_base64 = input_data.image_base64
        else:
            test_image_base64 = _get_test_image_base64()
            if not test_image_base64:
                return ProviderTestResult(
                    success=False,
                    error="Không tìm thấy file test image tại src/app/config/assets/images/image-test.jpg",
                    error_code="TEST_FILE_NOT_FOUND",
                )

        # Get question - from input or default
        test_question = (
            input_data.question
            if input_data and input_data.question
            else "Mô tả ngắn gọn hình ảnh này."
        )

        # Create instance
        start_time = time.time()
        vllm_instance = vllm.create_instance(vllm_type, config)

        response = vllm_instance.response(test_question, test_image_base64)

        latency_ms = int((time.time() - start_time) * 1000)

        if response:
            return ProviderTestResult(
                success=True,
                message="VLLM provider hoạt động bình thường",
                latency_ms=latency_ms,
                output=ProviderTestOutput(
                    text=response[:200] if len(response) > 200 else response,
                ),
            )
        else:
            return ProviderTestResult(
                success=False,
                error="Không nhận được response từ VLLM",
                error_code="NO_RESPONSE",
            )

    except Exception as e:
        error_str = str(e).lower()

        if (
            "authentication" in error_str
            or "api key" in error_str
            or "401" in error_str
        ):
            return ProviderTestResult(
                success=False,
                error="API key không hợp lệ",
                error_code="AUTH_ERROR",
            )
        elif "connection" in error_str or "timeout" in error_str:
            return ProviderTestResult(
                success=False,
                error="Không thể kết nối tới API",
                error_code="CONNECTION_ERROR",
            )
        elif "model" in error_str and "not found" in error_str:
            return ProviderTestResult(
                success=False,
                error="Model không tồn tại hoặc không có quyền truy cập",
                error_code="MODEL_NOT_FOUND",
            )
        else:
            logger.bind(tag=TAG).error(f"VLLM test error: {e}")
            return ProviderTestResult(
                success=False,
                error=str(e),
                error_code="UNKNOWN_ERROR",
            )


async def test_memory_provider(config: dict[str, Any]) -> ProviderTestResult:
    """
    Test Memory provider by initializing and querying.

    Verifies:
    - Provider can be initialized
    - Connection to memory backend works (if applicable)
    - Basic query doesn't throw errors
    """
    try:
        from app.ai.utils import memory

        memory_type = config.get("type")
        if not memory_type:
            return ProviderTestResult(
                success=False,
                error="Config thiếu field 'type'",
                error_code="INVALID_CONFIG",
            )

        start_time = time.time()

        # Special case: nomem type always succeeds (no actual memory)
        if memory_type == "nomem":
            return ProviderTestResult(
                success=True,
                message="Memory provider (nomem) không yêu cầu kết nối",
                latency_ms=0,
                output=ProviderTestOutput(
                    metadata={"type": "nomem", "note": "No memory storage"},
                ),
            )

        # Create instance
        memory_instance = memory.create_instance(memory_type, config, None)

        if not memory_instance:
            return ProviderTestResult(
                success=False,
                error="Không thể khởi tạo Memory instance",
                error_code="INIT_ERROR",
            )

        # Initialize with test role
        memory_instance.init_memory(
            role_id="test_provider_check",
            llm=None,  # LLM not required for connection test
        )

        # Try a simple query to verify connection
        try:
            result = await memory_instance.query_memory("test query")
            latency_ms = int((time.time() - start_time) * 1000)

            return ProviderTestResult(
                success=True,
                message="Memory provider hoạt động bình thường",
                latency_ms=latency_ms,
                output=ProviderTestOutput(
                    metadata={
                        "type": memory_type,
                        "query_result_length": len(result) if result else 0,
                    },
                ),
            )
        except NotImplementedError:
            # Some memory providers may not implement query_memory
            latency_ms = int((time.time() - start_time) * 1000)
            return ProviderTestResult(
                success=True,
                message="Memory provider khởi tạo thành công",
                latency_ms=latency_ms,
                output=ProviderTestOutput(
                    metadata={"type": memory_type, "note": "Query not implemented"},
                ),
            )

    except Exception as e:
        error_str = str(e).lower()

        if (
            "authentication" in error_str
            or "api key" in error_str
            or "401" in error_str
        ):
            return ProviderTestResult(
                success=False,
                error="API key không hợp lệ",
                error_code="AUTH_ERROR",
            )
        elif "connection" in error_str or "timeout" in error_str:
            return ProviderTestResult(
                success=False,
                error="Không thể kết nối tới memory backend",
                error_code="CONNECTION_ERROR",
            )
        else:
            logger.bind(tag=TAG).error(f"Memory test error: {e}")
            return ProviderTestResult(
                success=False,
                error=str(e),
                error_code="UNKNOWN_ERROR",
            )
