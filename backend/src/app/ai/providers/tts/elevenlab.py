import requests
from app.ai.utils.util import check_model_key
from app.ai.providers.tts.base import TTSProviderBase
from app.core.logger import setup_logging

TAG = __name__
logger = setup_logging()


class TTSProvider(TTSProviderBase):
    """
    ElevenLabs TTS Provider
    API Reference: https://elevenlabs.io/docs/api/text-to-speech

    POST https://api.elevenlabs.io/v1/text-to-speech/:voice_id
    """

    def __init__(self, config, delete_audio_file):
        super().__init__(config, delete_audio_file)
        self.api_key = config.get("api_key")
        self.api_url = config.get(
            "api_url", "https://api.elevenlabs.io/v1/text-to-speech"
        )
        self.voice_id = config.get("voice_id", "JBFqnCBsd6RMkjVDRZzb")
        self.model_id = config.get("model_id", "eleven_multilingual_v2")

        # Format specification (mp3_44100_128, mp3_22050_32, pcm_16000, pcm_22050, pcm_24000, pcm_44100, ulaw_8000)
        self.output_format = config.get("format", "mp3_44100_128")

        # Xác định file type dựa trên output_format
        if "mp3" in self.output_format:
            self.audio_file_type = "mp3"
        elif "pcm" in self.output_format:
            self.audio_file_type = "pcm"
        elif "ulaw" in self.output_format:
            self.audio_file_type = "ulaw"
        else:
            self.audio_file_type = "wav"

        # Xử lý language_code (optional)
        self.language_code = config.get("language_code", None)

        # Voice settings (optional)
        stability = config.get("stability", "0.5")
        self.stability = float(stability) if stability else 0.5

        clarity = config.get("clarity_boost", "0.75")
        self.clarity_boost = float(clarity) if clarity else 0.75

        self.output_file = config.get("output_dir", "tmp/")
        model_key_msg = check_model_key("TTS_ElevenLabs", self.api_key)
        if model_key_msg:
            logger.bind(tag=TAG).error(model_key_msg)

    async def text_to_speak(self, text, output_file):
        """
        Gọi ElevenLabs API để chuyển đổi text thành speech

        POST /v1/text-to-speech/:voice_id

        Required:
            - text: Text cần chuyển đổi

        Optional:
            - model_id: "eleven_monolingual_v1", "eleven_multilingual_v1", "eleven_multilingual_v2"
            - language_code: "en", "vi", etc.

        Args:
            text: Text cần chuyển đổi
            output_file: Đường dẫn file để lưu audio (nếu không, trả về bytes)

        Returns:
            bytes: Audio data nếu output_file là None
        """
        try:
            # URL: https://api.elevenlabs.io/v1/text-to-speech/:voice_id?output_format=mp3_44100_128
            url = f"{self.api_url}/{self.voice_id}?output_format={self.output_format}"

            headers = {
                "xi-api-key": self.api_key,
                "Content-Type": "application/json",
            }

            # Dữ liệu yêu cầu (text là bắt buộc)
            data = {
                "text": text,
                "model_id": self.model_id,
            }

            # Thêm voice_settings nếu có
            voice_settings = {}
            if self.stability is not None:
                voice_settings["stability"] = self.stability
            if self.clarity_boost is not None:
                voice_settings["similarity_boost"] = self.clarity_boost

            if voice_settings:
                data["voice_settings"] = voice_settings

            # Thêm language_code nếu có
            if self.language_code:
                data["language_code"] = self.language_code

            response = requests.post(url, json=data, headers=headers, timeout=30)

            if response.status_code == 200:
                if output_file:
                    with open(output_file, "wb") as audio_file:
                        audio_file.write(response.content)
                else:
                    return response.content
            elif response.status_code == 401:
                raise Exception(
                    f"ElevenLabs TTS thất bại: Unauthorized - API key không hợp lệ. {response.text}"
                )
            elif response.status_code == 429:
                raise Exception(
                    f"ElevenLabs TTS thất bại: Rate limit exceeded. Vui lòng thử lại sau. {response.text}"
                )
            elif response.status_code == 400:
                raise Exception(
                    f"ElevenLabs TTS thất bại: Bad request - Kiểm tra text hoặc voice_id. {response.text}"
                )
            else:
                raise Exception(
                    f"ElevenLabs TTS thất bại: {response.status_code} - {response.text}"
                )

        except requests.exceptions.Timeout:
            raise Exception("ElevenLabs TTS timeout: Yêu cầu vượt quá thời gian chờ")
        except requests.exceptions.ConnectionError as e:
            raise Exception(f"ElevenLabs TTS connection error: {e}")
        except Exception as e:
            logger.bind(tag=TAG).error(f"ElevenLabs TTS error: {e}")
            raise
