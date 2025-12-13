"""
Provider Schema Registry - Single source of truth for provider field schemas.

Định nghĩa metadata cho tất cả provider types, dùng cho:
- UI form rendering (dynamic)
- Config validation
- API documentation
"""

from enum import Enum
from typing import Any

from pydantic import BaseModel


class FieldType(str, Enum):
    """Supported field types for provider config."""

    STRING = "string"
    SECRET = "secret"
    NUMBER = "number"
    INTEGER = "integer"
    BOOLEAN = "boolean"
    SELECT = "select"
    MULTISELECT = "multiselect"
    TEXTAREA = "textarea"


class SelectOption(BaseModel):
    """Option for select/multiselect fields."""

    value: str
    label: str


class ProviderFieldSchema(BaseModel):
    """Schema definition for a single provider config field."""

    name: str
    label: str
    type: FieldType
    required: bool = False
    default: Any = None
    description: str | None = None
    placeholder: str | None = None
    # Validation constraints
    min: float | None = None
    max: float | None = None
    step: float | None = None
    min_length: int | None = None
    max_length: int | None = None
    pattern: str | None = None  # regex pattern
    # Select options
    options: list[SelectOption] | None = None


class ProviderTypeSchema(BaseModel):
    """Schema definition for a provider type."""

    label: str
    description: str | None = None
    fields: list[ProviderFieldSchema]


# =============================================================================
# LLM Provider Schemas
# =============================================================================

LLM_OPENAI_SCHEMA = ProviderTypeSchema(
    label="OpenAI Compatible",
    description="OpenAI API hoặc các API tương thích (GitHub Copilot, Groq, Together, etc.)",
    fields=[
        ProviderFieldSchema(
            name="model_name",
            label="Model Name",
            type=FieldType.STRING,
            required=True,
            placeholder="gpt-4.1",
            description="Tên model sử dụng (vd: gpt-4.1, gpt-3.5-turbo)",
        ),
        ProviderFieldSchema(
            name="api_key",
            label="API Key",
            type=FieldType.SECRET,
            required=True,
            description="API key để xác thực",
        ),
        ProviderFieldSchema(
            name="base_url",
            label="Base URL",
            type=FieldType.STRING,
            required=False,
            default="https://api.openai.com/v1",
            placeholder="https://api.openai.com/v1",
            description="URL endpoint của API (để trống nếu dùng OpenAI mặc định)",
        ),
        ProviderFieldSchema(
            name="temperature",
            label="Temperature",
            type=FieldType.NUMBER,
            required=False,
            default=0.7,
            min=0,
            max=2,
            step=0.1,
            description="Độ sáng tạo của model (0 = deterministic, 2 = very creative)",
        ),
        ProviderFieldSchema(
            name="max_tokens",
            label="Max Tokens",
            type=FieldType.INTEGER,
            required=False,
            default=4000,
            min=1,
            max=128000,
            description="Số token tối đa cho response",
        ),
        ProviderFieldSchema(
            name="top_p",
            label="Top P",
            type=FieldType.NUMBER,
            required=False,
            default=1.0,
            min=0,
            max=1,
            step=0.1,
            description="Nucleus sampling threshold",
        ),
        ProviderFieldSchema(
            name="frequency_penalty",
            label="Frequency Penalty",
            type=FieldType.NUMBER,
            required=False,
            default=0,
            min=-2,
            max=2,
            step=0.1,
            description="Penalty cho việc lặp lại từ (-2 to 2)",
        ),
        ProviderFieldSchema(
            name="timeout",
            label="Timeout (seconds)",
            type=FieldType.INTEGER,
            required=False,
            default=300,
            min=1,
            max=600,
            description="Thời gian chờ tối đa cho request",
        ),
    ],
)

LLM_GEMINI_SCHEMA = ProviderTypeSchema(
    label="Google Gemini",
    description="Google Gemini API (Gemini Pro, Flash, etc.)",
    fields=[
        ProviderFieldSchema(
            name="api_key",
            label="API Key",
            type=FieldType.SECRET,
            required=True,
            description="Google AI API key",
        ),
        ProviderFieldSchema(
            name="model_name",
            label="Model",
            type=FieldType.STRING,
            required=True,
            default="gemini-2.0-flash",
            description="Model Gemini sử dụng (vd: gemini-2.0-flash, gemini-1.5-pro, etc.)",
        ),
        ProviderFieldSchema(
            name="timeout",
            label="Timeout (seconds)",
            type=FieldType.INTEGER,
            required=False,
            default=120,
            min=1,
            max=300,
            description="Thời gian chờ tối đa",
        ),
    ],
)

# =============================================================================
# TTS Provider Schemas
# =============================================================================

TTS_EDGE_SCHEMA = ProviderTypeSchema(
    label="Microsoft Edge TTS",
    description="Free TTS từ Microsoft Edge (không cần API key)",
    fields=[
        ProviderFieldSchema(
            name="voice",
            label="Voice",
            type=FieldType.SELECT,
            required=True,
            default="vi-VN-HoaiMyNeural",
            options=[
                SelectOption(
                    value="vi-VN-HoaiMyNeural", label="Hoài My (Nữ - Việt Nam)"
                ),
                SelectOption(
                    value="vi-VN-NamMinhNeural", label="Nam Minh (Nam - Việt Nam)"
                ),
                SelectOption(value="en-US-JennyNeural", label="Jenny (Nữ - US)"),
                SelectOption(value="en-US-GuyNeural", label="Guy (Nam - US)"),
                SelectOption(value="en-GB-SoniaNeural", label="Sonia (Nữ - UK)"),
                SelectOption(value="ja-JP-NanamiNeural", label="Nanami (Nữ - Japan)"),
                SelectOption(
                    value="zh-CN-XiaoxiaoNeural", label="Xiaoxiao (Nữ - China)"
                ),
            ],
            description="Chọn giọng nói",
        ),
    ],
)

TTS_GOOGLE_SCHEMA = ProviderTypeSchema(
    label="Google Cloud TTS",
    description="Google Cloud Text-to-Speech API (cần API key)",
    fields=[
        ProviderFieldSchema(
            name="api_key",
            label="API Key",
            type=FieldType.SECRET,
            required=True,
            description="Google Cloud API key",
        ),
        ProviderFieldSchema(
            name="voice_name",
            label="Voice Name",
            type=FieldType.STRING,
            required=False,
            default="vi-VN-Chirp3-HD-Aoede",
            placeholder="vi-VN-Chirp3-HD-Aoede",
            description="Tên voice (xem Google Cloud TTS docs)",
        ),
        ProviderFieldSchema(
            name="model_name",
            label="Model",
            type=FieldType.STRING,
            required=True,
            default="gemini-2.5-flash-tts",
            placeholder="gemini-2.5-flash-tts",
            description="Model TTS (vd: gemini-2.5-flash-tts)",
        ),
        ProviderFieldSchema(
            name="language_code",
            label="Language Code",
            type=FieldType.STRING,
            required=False,
            default="vi-VN",
            placeholder="vi-VN",
            description="Mã ngôn ngữ (vd: vi-VN, en-US)",
        ),
        ProviderFieldSchema(
            name="speaking_rate",
            label="Speaking Rate",
            type=FieldType.NUMBER,
            required=False,
            default=1.0,
            min=0.25,
            max=4.0,
            step=0.1,
            description="Tốc độ nói (0.25 - 4.0)",
        ),
        ProviderFieldSchema(
            name="pitch",
            label="Pitch",
            type=FieldType.NUMBER,
            required=False,
            default=0,
            min=-20,
            max=20,
            step=1,
            description="Cao độ giọng (-20 to 20)",
        ),
        ProviderFieldSchema(
            name="audio_encoding",
            label="Audio Encoding",
            type=FieldType.SELECT,
            required=False,
            default="MP3",
            options=[
                SelectOption(value="MP3", label="MP3"),
                SelectOption(value="LINEAR16", label="WAV (LINEAR16)"),
                SelectOption(value="OGG_OPUS", label="OGG Opus"),
            ],
            description="Định dạng audio output",
        ),
    ],
)

TTS_OPENAI_SCHEMA = ProviderTypeSchema(
    label="OpenAI TTS",
    description="OpenAI Text-to-Speech API",
    fields=[
        ProviderFieldSchema(
            name="api_key",
            label="API Key",
            type=FieldType.SECRET,
            required=True,
            description="OpenAI API key",
        ),
        ProviderFieldSchema(
            name="model",
            label="Model",
            type=FieldType.STRING,
            required=True,
            default="tts-1",
            placeholder="tts-1",
            description="Model TTS (tts-1 hoặc tts-1-hd)",
        ),
        ProviderFieldSchema(
            name="voice",
            label="Voice",
            type=FieldType.SELECT,
            required=False,
            default="alloy",
            options=[
                SelectOption(value="alloy", label="Alloy"),
                SelectOption(value="echo", label="Echo"),
                SelectOption(value="fable", label="Fable"),
                SelectOption(value="onyx", label="Onyx"),
                SelectOption(value="nova", label="Nova"),
                SelectOption(value="shimmer", label="Shimmer"),
            ],
            description="Giọng nói",
        ),
        ProviderFieldSchema(
            name="speed",
            label="Speed",
            type=FieldType.NUMBER,
            required=False,
            default=1.0,
            min=0.25,
            max=4.0,
            step=0.1,
            description="Tốc độ nói (0.25 - 4.0)",
        ),
        ProviderFieldSchema(
            name="format",
            label="Format",
            type=FieldType.SELECT,
            required=False,
            default="wav",
            options=[
                SelectOption(value="wav", label="WAV"),
                SelectOption(value="mp3", label="MP3"),
                SelectOption(value="aac", label="AAC"),
                SelectOption(value="flac", label="FLAC"),
            ],
            description="Định dạng audio output",
        ),
        ProviderFieldSchema(
            name="api_url",
            label="API URL",
            type=FieldType.STRING,
            required=False,
            default="https://api.openai.com/v1/audio/speech",
            placeholder="https://api.openai.com/v1/audio/speech",
            description="OpenAI API endpoint (để trống nếu dùng mặc định)",
        ),
    ],
)

TTS_ELEVENLAB_SCHEMA = ProviderTypeSchema(
    label="ElevenLabs TTS",
    description="ElevenLabs Text-to-Speech API",
    fields=[
        ProviderFieldSchema(
            name="api_key",
            label="API Key",
            type=FieldType.SECRET,
            required=True,
            description="ElevenLabs API key",
        ),
        ProviderFieldSchema(
            name="voice_id",
            label="Voice ID",
            type=FieldType.STRING,
            required=False,
            default=None,
            placeholder="JBFqnCBsd6RMkjVDRZzb",
            description="Voice ID (xem ElevenLabs voices list)",
        ),
        ProviderFieldSchema(
            name="model_id",
            label="Model",
            type=FieldType.STRING,
            required=True,
            default="eleven_flash_v2_5",
            # options=[
            #     SelectOption(value="eleven_monolingual_v1", label="Monolingual V1"),
            #     SelectOption(value="eleven_multilingual_v1", label="Multilingual V1"),
            #     SelectOption(
            #         value="eleven_multilingual_v2",
            #         label="Multilingual V2 (Recommended)",
            #     ),
            # ],
            description="Model ID (eleven_monolingual_v1, eleven_multilingual_v1, eleven_multilingual_v2, eleven_flash_v2_5)",
        ),
        ProviderFieldSchema(
            name="format",
            label="Audio Format",
            type=FieldType.SELECT,
            required=False,
            default="mp3_44100_128",
            options=[
                SelectOption(value="mp3_44100_128", label="MP3 44100Hz 128kbps"),
                SelectOption(value="mp3_22050_32", label="MP3 22050Hz 32kbps"),
                SelectOption(value="pcm_16000", label="PCM 16000Hz"),
                SelectOption(value="pcm_22050", label="PCM 22050Hz"),
                SelectOption(value="pcm_24000", label="PCM 24000Hz"),
                SelectOption(value="pcm_44100", label="PCM 44100Hz"),
                SelectOption(value="ulaw_8000", label="ULAW 8000Hz"),
            ],
            description="Định dạng audio",
        ),
        ProviderFieldSchema(
            name="stability",
            label="Stability",
            type=FieldType.NUMBER,
            required=False,
            default=0.5,
            min=0.0,
            max=1.0,
            step=0.1,
            description="Độ ổn định giọng nói (0-1)",
        ),
        ProviderFieldSchema(
            name="clarity_boost",
            label="Clarity Boost",
            type=FieldType.NUMBER,
            required=False,
            default=0.75,
            min=0.0,
            max=1.0,
            step=0.1,
            description="Độ tăng cường độ rõ (0-1)",
        ),
        ProviderFieldSchema(
            name="language_code",
            label="Language Code",
            type=FieldType.STRING,
            required=False,
            placeholder="en",
            description="Mã ngôn ngữ (optional, vd: en, vi)",
        ),
        ProviderFieldSchema(
            name="api_url",
            label="API URL",
            type=FieldType.STRING,
            required=False,
            default="https://api.elevenlabs.io/v1/text-to-speech",
            placeholder="https://api.elevenlabs.io/v1/text-to-speech",
            description="ElevenLabs API endpoint",
        ),
    ],
)

TTS_DEEPGRAM_SCHEMA = ProviderTypeSchema(
    label="Deepgram TTS",
    description="Deepgram Text-to-Speech API",
    fields=[
        ProviderFieldSchema(
            name="api_key",
            label="API Key",
            type=FieldType.SECRET,
            required=True,
            description="Deepgram API key",
        ),
        ProviderFieldSchema(
            name="model",
            label="Model",
            type=FieldType.STRING,
            required=True,
            default="aura-asteria-en",
            placeholder="aura-asteria-en",
            description="Voice model ID (vd: aura-asteria-en, aura-luna-en)",
        ),
        ProviderFieldSchema(
            name="encoding",
            label="Encoding",
            type=FieldType.SELECT,
            required=False,
            default="linear16",
            options=[
                SelectOption(value="linear16", label="Linear16 (WAV)"),
                SelectOption(value="mp3", label="MP3"),
                SelectOption(value="opus", label="Opus"),
                SelectOption(value="flac", label="FLAC"),
            ],
            description="Audio encoding format",
        ),
        ProviderFieldSchema(
            name="sample_rate",
            label="Sample Rate",
            type=FieldType.INTEGER,
            required=False,
            default=16000,
            min=8000,
            max=48000,
            description="Sample rate (Hz)",
        ),
    ],
)

# =============================================================================
# ASR Provider Schemas
# =============================================================================

ASR_OPENAI_SCHEMA = ProviderTypeSchema(
    label="OpenAI Whisper",
    description="OpenAI Whisper ASR API (hoặc Groq Whisper)",
    fields=[
        ProviderFieldSchema(
            name="api_key",
            label="API Key",
            type=FieldType.SECRET,
            required=True,
            description="OpenAI hoặc Groq API key",
        ),
        ProviderFieldSchema(
            name="base_url",
            label="Base URL",
            type=FieldType.STRING,
            required=False,
            default=None,
            placeholder="https://api.groq.com/openai/v1/audio/transcriptions",
            description="Custom API URL (để trống nếu dùng OpenAI)",
        ),
        ProviderFieldSchema(
            name="model_name",
            label="Model",
            type=FieldType.STRING,
            required=True,
            default="whisper-1",
            options=[
                SelectOption(value="whisper-1", label="Whisper (OpenAI)"),
                SelectOption(value="whisper-large-v3", label="Whisper Large V3 (Groq)"),
                SelectOption(
                    value="whisper-large-v3-turbo",
                    label="Whisper Large V3 Turbo (Groq)",
                ),
            ],
            description="Chọn model Whisper",
        ),
    ],
)

ASR_DEEPGRAM_SCHEMA = ProviderTypeSchema(
    label="Deepgram ASR",
    description="Deepgram Speech Recognition API",
    fields=[
        ProviderFieldSchema(
            name="api_key",
            label="API Key",
            type=FieldType.SECRET,
            required=True,
            description="Deepgram API key",
        ),
        ProviderFieldSchema(
            name="model",
            label="Model",
            type=FieldType.SELECT,
            required=False,
            default="nova-2",
            options=[
                SelectOption(value="nova-2", label="Nova 2 (Recommended)"),
                SelectOption(value="nova", label="Nova"),
                SelectOption(value="enhanced", label="Enhanced"),
                SelectOption(value="base", label="Base"),
            ],
            description="Chọn model ASR",
        ),
        ProviderFieldSchema(
            name="language",
            label="Language",
            type=FieldType.SELECT,
            required=False,
            default="vi",
            options=[
                SelectOption(value="vi", label="Vietnamese"),
                SelectOption(value="en", label="English"),
                SelectOption(value="en-US", label="English (US)"),
                SelectOption(value="en-GB", label="English (UK)"),
                SelectOption(value="ja", label="Japanese"),
                SelectOption(value="zh", label="Chinese"),
                SelectOption(value="ko", label="Korean"),
            ],
            description="Ngôn ngữ nhận diện",
        ),
        ProviderFieldSchema(
            name="smart_format",
            label="Smart Format",
            type=FieldType.BOOLEAN,
            required=False,
            default=True,
            description="Tự động format (số, ngày, etc.)",
        ),
    ],
)

ASR_SHERPA_ONNX_SCHEMA = ProviderTypeSchema(
    label="Sherpa ONNX (Local)",
    description="Local ASR với Sherpa ONNX - không cần internet",
    fields=[
        ProviderFieldSchema(
            name="repo_id",
            label="HuggingFace Repo ID",
            type=FieldType.STRING,
            required=False,
            default="hynt/Zipformer-30M-RNNT-6000h",
            placeholder="hynt/Zipformer-30M-RNNT-6000h",
            description="HuggingFace repository ID cho model",
        ),
        ProviderFieldSchema(
            name="model_dir",
            label="Model Directory",
            type=FieldType.STRING,
            required=False,
            placeholder="sherpa_onnx_local",
            description="Thư mục lưu model (tương đối với models_data)",
        ),
        ProviderFieldSchema(
            name="use_int8",
            label="Use INT8",
            type=FieldType.BOOLEAN,
            required=False,
            default=True,
            description="Sử dụng INT8 quantization (tiết kiệm bộ nhớ)",
        ),
        ProviderFieldSchema(
            name="num_threads",
            label="Num Threads",
            type=FieldType.INTEGER,
            required=False,
            default=2,
            min=1,
            max=16,
            description="Số CPU threads",
        ),
        ProviderFieldSchema(
            name="decoding_method",
            label="Decoding Method",
            type=FieldType.SELECT,
            required=False,
            default="greedy_search",
            options=[
                SelectOption(value="greedy_search", label="Greedy Search (Fast)"),
                SelectOption(
                    value="modified_beam_search", label="Beam Search (Accurate)"
                ),
            ],
            description="Phương pháp decode",
        ),
        ProviderFieldSchema(
            name="encoder_filename",
            label="Encoder Filename",
            type=FieldType.STRING,
            required=False,
            placeholder="encoder-epoch-20-avg-10.int8.onnx",
            description="Tên file encoder ONNX (bắt buộc nếu dùng custom repo)",
        ),
        ProviderFieldSchema(
            name="decoder_filename",
            label="Decoder Filename",
            type=FieldType.STRING,
            required=False,
            placeholder="decoder-epoch-20-avg-10.onnx",
            description="Tên file decoder ONNX (bắt buộc nếu dùng custom repo)",
        ),
        ProviderFieldSchema(
            name="joiner_filename",
            label="Joiner Filename",
            type=FieldType.STRING,
            required=False,
            placeholder="joiner-epoch-20-avg-10.int8.onnx",
            description="Tên file joiner ONNX (bắt buộc nếu dùng custom repo)",
        ),
        ProviderFieldSchema(
            name="tokens_filename",
            label="Tokens Filename",
            type=FieldType.STRING,
            required=False,
            default="config.json",
            placeholder="config.json",
            description="Tên file tokens/config JSON",
        ),
    ],
)

ASR_CHUNKFORMER_SCHEMA = ProviderTypeSchema(
    label="Chunkformer (Local)",
    description="Local ASR với Chunkformer RNNT - tối ưu cho tiếng Việt",
    fields=[
        ProviderFieldSchema(
            name="repo_id",
            label="HuggingFace Repo ID",
            type=FieldType.STRING,
            required=False,
            default="khanhld/chunkformer-rnnt-large-vie",
            placeholder="khanhld/chunkformer-rnnt-large-vie",
            description="HuggingFace repository ID cho model",
        ),
        ProviderFieldSchema(
            name="model_dir",
            label="Model Directory",
            type=FieldType.STRING,
            required=False,
            default="chunkformer",
            placeholder="chunkformer",
            description="Thư mục lưu model (tương đối với models_data)",
        ),
        ProviderFieldSchema(
            name="chunk_size",
            label="Chunk Size",
            type=FieldType.INTEGER,
            required=False,
            default=64,
            min=32,
            max=256,
            description="Kích thước chunk (64: cân bằng, 128: chính xác hơn)",
        ),
        ProviderFieldSchema(
            name="left_context_size",
            label="Left Context Size",
            type=FieldType.INTEGER,
            required=False,
            default=128,
            min=64,
            max=512,
            description="Context bên trái (128: mặc định, 256: chính xác hơn)",
        ),
        ProviderFieldSchema(
            name="right_context_size",
            label="Right Context Size",
            type=FieldType.INTEGER,
            required=False,
            default=128,
            min=64,
            max=512,
            description="Context bên phải (128: mặc định, 256: chính xác hơn)",
        ),
        ProviderFieldSchema(
            name="total_batch_duration",
            label="Total Batch Duration",
            type=FieldType.INTEGER,
            required=False,
            default=1800,
            min=600,
            max=7200,
            description="Tổng thời lượng batch (giây)",
        ),
    ],
)

ASR_WHISPER_CPP_SCHEMA = ProviderTypeSchema(
    label="Whisper.cpp (Local)",
    description="Local ASR với whisper.cpp - hỗ trợ đa ngôn ngữ, song ngữ",
    fields=[
        ProviderFieldSchema(
            name="model_name",
            label="Model",
            type=FieldType.SELECT,
            required=False,
            default="base",
            options=[
                SelectOption(value="tiny", label="Tiny (~75MB, nhanh nhất)"),
                SelectOption(value="base", label="Base (~142MB, cân bằng)"),
                SelectOption(value="small", label="Small (~466MB, khuyên dùng)"),
                SelectOption(value="medium", label="Medium (~1.5GB, chính xác)"),
                SelectOption(value="large-v2", label="Large V2 (~3GB)"),
                SelectOption(value="large-v3", label="Large V3 (~3GB, tốt nhất)"),
            ],
            description="Chọn model Whisper (small+ cho song ngữ)",
        ),
        ProviderFieldSchema(
            name="language",
            label="Language",
            type=FieldType.SELECT,
            required=False,
            default="vi",
            options=[
                SelectOption(value="vi", label="Vietnamese (ổn định)"),
                SelectOption(value="en", label="English"),
                SelectOption(value="auto", label="Auto-detect (cần model small+)"),
                SelectOption(value="ja", label="Japanese"),
                SelectOption(value="zh", label="Chinese"),
                SelectOption(value="ko", label="Korean"),
            ],
            description="Ngôn ngữ nhận diện (auto: song ngữ, cần model small+)",
        ),
        ProviderFieldSchema(
            name="initial_prompt",
            label="Initial Prompt",
            type=FieldType.TEXTAREA,
            required=False,
            placeholder="Đây là đoạn hội thoại tiếng Việt có thể chứa một số từ tiếng Anh.",
            description="Hint ngôn ngữ để giảm hallucination khi dùng auto",
        ),
        ProviderFieldSchema(
            name="model_dir",
            label="Model Directory",
            type=FieldType.STRING,
            required=False,
            default="whisper_cpp",
            placeholder="whisper_cpp",
            description="Thư mục lưu model (tương đối với models_data)",
        ),
        ProviderFieldSchema(
            name="n_threads",
            label="Num Threads",
            type=FieldType.INTEGER,
            required=False,
            default=4,
            min=1,
            max=16,
            description="Số CPU threads",
        ),
        ProviderFieldSchema(
            name="print_realtime",
            label="Print Realtime",
            type=FieldType.BOOLEAN,
            required=False,
            default=False,
            description="In kết quả realtime (debug)",
        ),
        ProviderFieldSchema(
            name="print_progress",
            label="Print Progress",
            type=FieldType.BOOLEAN,
            required=False,
            default=False,
            description="In tiến trình (debug)",
        ),
    ],
)

# =============================================================================
# VLLM Provider Schemas (Vision LLM)
# =============================================================================

VLLM_OPENAI_SCHEMA = ProviderTypeSchema(
    label="OpenAI Compatible Vision",
    description="OpenAI Vision API hoặc các API tương thích (GPT-4V, GLM-4V, etc.)",
    fields=[
        ProviderFieldSchema(
            name="model_name",
            label="Model Name",
            type=FieldType.STRING,
            required=True,
            placeholder="gpt-4-vision-preview",
            description="Tên model vision (vd: gpt-4-vision-preview, glm-4v-flash)",
        ),
        ProviderFieldSchema(
            name="api_key",
            label="API Key",
            type=FieldType.SECRET,
            required=True,
            description="API key để xác thực",
        ),
        ProviderFieldSchema(
            name="base_url",
            label="Base URL",
            type=FieldType.STRING,
            required=False,
            default="https://api.openai.com/v1",
            placeholder="https://api.openai.com/v1",
            description="URL endpoint của API",
        ),
        ProviderFieldSchema(
            name="temperature",
            label="Temperature",
            type=FieldType.NUMBER,
            required=False,
            default=0.7,
            min=0,
            max=2,
            step=0.1,
            description="Độ ngẫu nhiên của output (0-2)",
        ),
        ProviderFieldSchema(
            name="max_tokens",
            label="Max Tokens",
            type=FieldType.INTEGER,
            required=False,
            default=4000,
            min=100,
            max=128000,
            description="Số tokens tối đa cho response",
        ),
    ],
)

# =============================================================================
# Memory Provider Schemas
# =============================================================================

MEMORY_NOMEM_SCHEMA = ProviderTypeSchema(
    label="No Memory",
    description="Không sử dụng memory - mỗi cuộc hội thoại độc lập",
    fields=[],  # Không cần config
)

MEMORY_MEM_LOCAL_SHORT_SCHEMA = ProviderTypeSchema(
    label="Local Short-term Memory",
    description="Memory ngắn hạn lưu local, sử dụng LLM để tóm tắt",
    fields=[
        ProviderFieldSchema(
            name="llm",
            label="LLM Provider Name",
            type=FieldType.STRING,
            required=False,
            placeholder="CopilotLLM",
            description="Tên LLM provider trong config để tóm tắt (nếu không set sẽ dùng mặc định)",
        ),
    ],
)

MEMORY_MEM0AI_SCHEMA = ProviderTypeSchema(
    label="Mem0 AI",
    description="Mem0 AI cloud service - memory-as-a-service",
    fields=[
        ProviderFieldSchema(
            name="api_key",
            label="API Key",
            type=FieldType.SECRET,
            required=True,
            description="Mem0 API key từ https://mem0.ai",
        ),
    ],
)

MEMORY_OPENMEMORY_SCHEMA = ProviderTypeSchema(
    label="OpenMemory",
    description="OpenMemory - self-hosted hoặc local memory với brain-inspired sectors",
    fields=[
        # Mode selection
        ProviderFieldSchema(
            name="mode",
            label="Mode",
            type=FieldType.SELECT,
            required=True,
            default="remote",
            options=[
                SelectOption(value="remote", label="Remote (API Server)"),
                SelectOption(value="local", label="Local (SQLite + Embeddings)"),
            ],
            description="Chọn local (offline) hoặc remote (API server)",
        ),
        # Remote mode fields
        ProviderFieldSchema(
            name="base_url",
            label="[Remote mode] Base URL",
            type=FieldType.STRING,
            required=False,
            placeholder="http://localhost:8080",
            description="[Remote mode] URL của OpenMemory server",
        ),
        ProviderFieldSchema(
            name="api_key",
            label="[Remote mode] API Key",
            type=FieldType.SECRET,
            required=False,
            description="[Remote mode] API key nếu server yêu cầu xác thực",
        ),
        # Local mode fields
        ProviderFieldSchema(
            name="local_path",
            label="[Local mode] Database Path",
            type=FieldType.STRING,
            required=False,
            default="./data/memory.sqlite",
            placeholder="./data/memory.sqlite",
            description="[Local mode] Đường dẫn file SQLite database",
        ),
        ProviderFieldSchema(
            name="tier",
            label="[Local mode] Tier",
            type=FieldType.SELECT,
            required=False,
            default="fast",
            options=[
                SelectOption(value="fast", label="Fast (synthetic embeddings)"),
                SelectOption(value="balanced", label="Balanced"),
                SelectOption(value="quality", label="Quality (API embeddings)"),
            ],
            description="[Local mode] Tier quality/speed trade-off",
        ),
        # Embeddings config (for local mode)
        ProviderFieldSchema(
            name="embeddings_provider",
            label="[Local mode] Embeddings Provider",
            type=FieldType.SELECT,
            required=False,
            default="synthetic",
            options=[
                SelectOption(value="synthetic", label="Synthetic (No API, fast)"),
                SelectOption(value="openai", label="OpenAI"),
                SelectOption(value="gemini", label="Google Gemini"),
            ],
            description="[Local mode] Provider cho embeddings",
        ),
        ProviderFieldSchema(
            name="embeddings_api_key",
            label="[Local mode] Embeddings API Key",
            type=FieldType.SECRET,
            required=False,
            description="[Local mode] API key cho OpenAI/Gemini embeddings",
        ),
        ProviderFieldSchema(
            name="embeddings_model",
            label="[Local mode] Embeddings Model",
            type=FieldType.STRING,
            required=False,
            placeholder="text-embedding-3-small",
            description="[Local mode] Model name (optional, ví dụ: text-embedding-3-small)",
        ),
        # Common fields
        ProviderFieldSchema(
            name="k",
            label="[Common] Memory Results (k)",
            type=FieldType.INTEGER,
            required=False,
            default=3,
            min=1,
            max=20,
            description="Số lượng memory results trả về khi query",
        ),
        ProviderFieldSchema(
            name="max_tokens",
            label="[Common] Max Tokens",
            type=FieldType.INTEGER,
            required=False,
            default=2000,
            min=500,
            max=8000,
            description="Max tokens khi LLM tóm tắt hội thoại",
        ),
    ],
)

# =============================================================================
# Intent Provider Schemas
# =============================================================================

INTENT_NOINTENT_SCHEMA = ProviderTypeSchema(
    label="No Intent",
    description="Không sử dụng intent detection - LLM trả lời trực tiếp",
    fields=[],
)

INTENT_FUNCTION_CALL_SCHEMA = ProviderTypeSchema(
    label="Function Call",
    description="Sử dụng OpenAI function calling để nhận dạng intent và gọi tools",
    fields=[
        ProviderFieldSchema(
            name="functions",
            label="Tools/Functions",
            type=FieldType.MULTISELECT,
            required=False,
            description="Danh sách system function names được phép sử dụng (ví dụ: 'get_weather', 'create_reminder'). Chỉ chấp nhận tên hàm từ system registry. Để trống = dùng tất cả tools mặc định.",
        ),
    ],
)

INTENT_INTENT_LLM_SCHEMA = ProviderTypeSchema(
    label="Intent LLM",
    description="Sử dụng LLM riêng để phân loại intent",
    fields=[
        ProviderFieldSchema(
            name="llm",
            label="LLM Provider",
            type=FieldType.STRING,
            required=True,
            placeholder="ChatGLMLLM",
            description="Tên LLM provider dùng để phân loại intent",
        ),
        ProviderFieldSchema(
            name="functions",
            label="Tools/Functions",
            type=FieldType.MULTISELECT,
            required=False,
            description="Danh sách tools được phép sử dụng. Có thể là UserTool UUID hoặc system tool name.",
        ),
    ],
)

# =============================================================================
# Provider Schema Registry
# =============================================================================

PROVIDER_SCHEMAS: dict[str, dict[str, ProviderTypeSchema]] = {
    "LLM": {
        "openai": LLM_OPENAI_SCHEMA,
        "gemini": LLM_GEMINI_SCHEMA,
    },
    "VLLM": {
        "openai": VLLM_OPENAI_SCHEMA,
    },
    "TTS": {
        "openai": TTS_OPENAI_SCHEMA,
        "elevenlab": TTS_ELEVENLAB_SCHEMA,
        "edge": TTS_EDGE_SCHEMA,
        "google": TTS_GOOGLE_SCHEMA,
        "deepgram": TTS_DEEPGRAM_SCHEMA,
    },
    "ASR": {
        "openai": ASR_OPENAI_SCHEMA,
        "deepgram": ASR_DEEPGRAM_SCHEMA,
        "sherpa_onnx_local": ASR_SHERPA_ONNX_SCHEMA,
        "chunkformer": ASR_CHUNKFORMER_SCHEMA,
        "whisper_cpp": ASR_WHISPER_CPP_SCHEMA,
    },
    "Memory": {
        "nomem": MEMORY_NOMEM_SCHEMA,
        "mem_local_short": MEMORY_MEM_LOCAL_SHORT_SCHEMA,
        "mem0ai": MEMORY_MEM0AI_SCHEMA,
        "openmemory": MEMORY_OPENMEMORY_SCHEMA,
    },
    "Intent": {
        "nointent": INTENT_NOINTENT_SCHEMA,
        "function_call": INTENT_FUNCTION_CALL_SCHEMA,
        "intent_llm": INTENT_INTENT_LLM_SCHEMA,
    },
}


def get_provider_schema(category: str, provider_type: str) -> ProviderTypeSchema | None:
    """Get schema for a specific provider type."""
    return PROVIDER_SCHEMAS.get(category, {}).get(provider_type)


def get_category_schemas(category: str) -> dict[str, ProviderTypeSchema]:
    """Get all schemas for a category."""
    return PROVIDER_SCHEMAS.get(category, {})


def get_all_schemas() -> dict[str, dict[str, ProviderTypeSchema]]:
    """Get all provider schemas."""
    return PROVIDER_SCHEMAS


def list_categories() -> list[str]:
    """List all available categories."""
    return list(PROVIDER_SCHEMAS.keys())


def list_provider_types(category: str) -> list[str]:
    """List all provider types for a category."""
    return list(PROVIDER_SCHEMAS.get(category, {}).keys())
