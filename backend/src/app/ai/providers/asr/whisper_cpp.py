import time
import wave
import os
from pathlib import Path
from app.core.logger import setup_logging
from typing import Optional, Tuple, List
from app.ai.providers.asr.dto.dto import InterfaceType
from app.ai.providers.asr.base import ASRProviderBase

import numpy as np
from pywhispercpp.model import Model

TAG = __name__
logger = setup_logging()


class ASRProvider(ASRProviderBase):
    """
    ASR Provider sử dụng pywhispercpp (whisper.cpp binding).
    Hỗ trợ các model: tiny, base, small, medium, large, large-v2, large-v3
    """

    def __init__(self, config: dict, delete_audio_file: bool):
        super().__init__()
        self.interface_type = InterfaceType.LOCAL

        # Lấy các thư mục từ path utilities
        from app.ai.utils.paths import get_models_data_dir, get_tmp_dir

        # Config cơ bản
        model_dir = config.get("model_dir")
        output_dir = config.get("output_dir")

        if not model_dir:
            model_dir = str(get_models_data_dir() / "whisper_cpp")
        else:
            # Nếu là relative path, gắn vào models_data_dir
            model_path = Path(model_dir)
            if not model_path.is_absolute():
                model_dir = str(get_models_data_dir() / model_dir)

        if not output_dir:
            output_dir = str(get_tmp_dir())
        else:
            output_dir = str(Path(output_dir).resolve())

        self.model_dir = str(model_dir)
        self.output_dir = str(output_dir)
        self.delete_audio_file = delete_audio_file

        # Model config
        # Các model hỗ trợ: tiny, base, small, medium, large, large-v2, large-v3
        self.model_name = config.get("model_name", "base")
        # Ngôn ngữ: "vi", "en", "auto" (tự detect), hoặc None (auto)
        # Dùng "auto" hoặc None cho song ngữ (bilingual)
        language = config.get("language", "auto")
        self.language = None if language in ("auto", None, "") else language

        # Performance config
        self.n_threads = config.get("n_threads", 4)  # Số threads
        self.print_realtime = config.get("print_realtime", False)
        self.print_progress = config.get("print_progress", False)

        # Initial prompt để hint ngôn ngữ, giảm hallucination
        # Ví dụ: "Đây là đoạn hội thoại tiếng Việt." cho tiếng Việt
        self.initial_prompt = config.get("initial_prompt", None)

        logger.bind(tag=TAG).debug(f"model_dir: {self.model_dir}")
        logger.bind(tag=TAG).debug(f"output_dir: {self.output_dir}")
        logger.bind(tag=TAG).debug(f"model_name: {self.model_name}")
        logger.bind(tag=TAG).debug(f"language: {self.language or 'auto-detect'}")
        logger.bind(tag=TAG).debug(f"n_threads: {self.n_threads}")

        # Đảm bảo directories tồn tại
        os.makedirs(self.output_dir, exist_ok=True)
        os.makedirs(self.model_dir, exist_ok=True)

        # Khởi tạo model
        try:
            logger.bind(tag=TAG).info(
                f"Đang khởi tạo whisper.cpp model '{self.model_name}'..."
            )

            # pywhispercpp tự động download model nếu chưa có
            # Nếu language=None → auto-detect (tốt cho song ngữ/bilingual)
            model_kwargs = {
                "model": self.model_name,
                "models_dir": self.model_dir,
                "n_threads": self.n_threads,
                "print_realtime": self.print_realtime,
                "print_progress": self.print_progress,
            }
            if self.language:
                model_kwargs["language"] = self.language

            self.model = Model(**model_kwargs)

            logger.bind(tag=TAG).info(
                f"Khởi tạo whisper.cpp provider thành công! Model: {self.model_name}"
            )

        except Exception as e:
            logger.bind(tag=TAG).error(f"Lỗi khi khởi tạo model: {str(e)}")
            raise

    def read_wave(self, wave_filename: str) -> Tuple[np.ndarray, int]:
        """
        Đọc file wave và trả về samples (float32) và sample rate.

        Args:
            wave_filename: đường dẫn đến file wave (mono, 16-bit)

        Returns:
            tuple chứa:
            - array 1-d kiểu np.float32 chứa samples (normalized [-1, 1])
            - sample rate của file wave
        """
        with wave.open(wave_filename) as f:
            assert (
                f.getnchannels() == 1
            ), f"expected mono audio, got {f.getnchannels()} channels"
            assert (
                f.getsampwidth() == 2
            ), f"expected 16-bit audio, got {f.getsampwidth()} bytes"

            num_samples = f.getnframes()
            samples = f.readframes(num_samples)
            samples_int16 = np.frombuffer(samples, dtype=np.int16)
            samples_float32 = samples_int16.astype(np.float32)
            samples_float32 = samples_float32 / 32768.0

            return samples_float32, f.getframerate()

    async def speech_to_text(
        self, opus_data: List[bytes], session_id: str, audio_format="opus"
    ) -> Tuple[Optional[str], Optional[str]]:
        """Chuyển đổi giọng nói thành text sử dụng whisper.cpp"""
        file_path = None
        try:
            # Lưu audio file
            start_time = time.time()
            if audio_format == "pcm":
                pcm_data = opus_data
            else:
                pcm_data = self.decode_opus(opus_data)

            file_path = self.save_audio_to_file(pcm_data, session_id)
            logger.bind(tag=TAG).debug(
                f"Lưu audio mất {time.time() - start_time:.3f}s | đường dẫn: {file_path}"
            )

            # Nhận diện giọng nói
            start_time = time.time()

            # Transcribe sử dụng pywhispercpp
            # initial_prompt giúp hint ngôn ngữ, giảm hallucination
            transcribe_kwargs = {}
            if self.initial_prompt:
                transcribe_kwargs["initial_prompt"] = self.initial_prompt

            segments = self.model.transcribe(file_path, **transcribe_kwargs)

            # Ghép tất cả segments thành text
            text = " ".join([segment.text for segment in segments]).strip().lower()

            logger.bind(tag=TAG).debug(
                f"Nhận diện mất {time.time() - start_time:.3f}s | kết quả: {text}"
            )

            return text, file_path

        except Exception as e:
            logger.bind(tag=TAG).error(f"Lỗi nhận diện giọng nói: {e}", exc_info=True)
            return "", file_path
        finally:
            # Xóa file tạm nếu cần
            if self.delete_audio_file and file_path and os.path.exists(file_path):
                try:
                    os.remove(file_path)
                    logger.bind(tag=TAG).debug(f"Đã xóa file tạm: {file_path}")
                except Exception as e:
                    logger.bind(tag=TAG).error(
                        f"Không thể xóa file: {file_path} | lỗi: {e}"
                    )
