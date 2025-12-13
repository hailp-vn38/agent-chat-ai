import os
import uuid
import requests
from datetime import datetime
from app.ai.providers.tts.base import TTSProviderBase
from app.core.logger import setup_logging

TAG = __name__
logger = setup_logging()


class TTSProvider(TTSProviderBase):
    """Google Cloud Text-to-Speech Provider sử dụng REST API"""

    def __init__(self, config, delete_audio_file):
        super().__init__(config, delete_audio_file)

        # Validate API Key
        self.api_key = config.get("api_key")
        if not self.api_key:
            raise ValueError("Cần cấu hình `api_key` cho Google Cloud TTS")

        # Các tham số cấu hình
        self.language_code = config.get("language_code", "vi-VN")
        self.voice_name = config.get("voice_name", "vi-VN-Standard-A")
        self.model_name = config.get(
            "model_name"
        )  # Optional: e.g., "gemini-2.5-flash-tts"
        self.pitch = config.get("pitch", 0)
        self.speaking_rate = config.get("speaking_rate", 1.0)
        self.audio_encoding = config.get("audio_encoding", "MP3")
        self.sample_rate_hz = config.get("sample_rate_hz", 16000)

        # Ánh xạ audio encoding sang file extension
        self.encoding_to_ext = {
            "LINEAR16": "wav",
            "MP3": "mp3",
            "OGG_OPUS": "opus",
            "MULAW": "wav",
            "ALAW": "wav",
        }

        self.audio_file_type = self.encoding_to_ext.get(self.audio_encoding, "mp3")
        self.google_tts_url = (
            "https://texttospeech.googleapis.com/v1beta1/text:synthesize"
        )

        logger.bind(tag=TAG).debug(
            f"Google Cloud TTS initialized: voice={self.voice_name}, "
            f"language={self.language_code}, encoding={self.audio_encoding}, "
            f"model={self.model_name if self.model_name else 'default'}"
        )

    def generate_filename(self, extension=None):
        if extension is None:
            extension = f".{self.audio_file_type}"
        return os.path.join(
            self.output_file,
            f"tts-{datetime.now().date()}@{uuid.uuid4().hex}{extension}",
        )

    async def text_to_speak(self, text, output_file):
        """Chuyển đổi text thành speech sử dụng Google Cloud TTS API"""
        try:
            # Chuẩn bị voice config
            voice_config = {
                "languageCode": self.language_code,
                "name": self.voice_name,
            }
            # Thêm modelName nếu được cấu hình
            if self.model_name:
                voice_config["modelName"] = self.model_name

            # Chuẩn bị audio config
            audio_config = {
                "audioEncoding": self.audio_encoding,
                "pitch": self.pitch,
                "speakingRate": self.speaking_rate,
            }
            # Thêm sampleRateHertz nếu không phải default
            if self.sample_rate_hz:
                audio_config["sampleRateHertz"] = self.sample_rate_hz

            # Chuẩn bị payload
            payload = {
                "input": {
                    "text": text,
                },
                "voice": voice_config,
                "audioConfig": audio_config,
            }

            # Chuẩn bị headers
            headers = {"Content-Type": "application/json"}

            # Chuẩn bị params với API Key
            params = {"key": self.api_key}

            # Gọi Google Cloud TTS API
            response = requests.post(
                self.google_tts_url,
                json=payload,
                params=params,
                headers=headers,
                timeout=30,
            )

            if response.status_code != 200:
                error_msg = f"Google Cloud TTS request failed: {response.status_code}"
                try:
                    error_detail = response.json()
                    error_msg += f" - {error_detail.get('error', {}).get('message', response.text)}"
                except:
                    error_msg += f" - {response.text}"

                logger.bind(tag=TAG).error(error_msg)
                raise Exception(error_msg)

            # Parse response
            response_data = response.json()
            audio_bytes = None

            try:
                # Audio content là base64 encoded
                import base64

                audio_content = response_data.get("audioContent")
                if not audio_content:
                    raise ValueError("No audioContent in response")

                audio_bytes = base64.b64decode(audio_content)
            except Exception as e:
                error_msg = f"Failed to decode audio content: {e}"
                logger.bind(tag=TAG).error(error_msg)
                raise Exception(error_msg)

            # Ghi file hoặc trả về bytes
            if output_file:
                os.makedirs(os.path.dirname(output_file), exist_ok=True)
                with open(output_file, "wb") as f:
                    f.write(audio_bytes)
                logger.bind(tag=TAG).debug(f"TTS file saved: {output_file}")
                return None
            else:
                return audio_bytes

        except requests.exceptions.Timeout:
            error_msg = "Google Cloud TTS request timeout"
            logger.bind(tag=TAG).error(error_msg)
            raise Exception(error_msg)
        except requests.exceptions.RequestException as e:
            error_msg = f"Google Cloud TTS request error: {e}"
            logger.bind(tag=TAG).error(error_msg)
            raise Exception(error_msg)
        except Exception as e:
            error_msg = f"Google Cloud TTS error: {e}"
            logger.bind(tag=TAG).error(error_msg)
            raise Exception(error_msg)
