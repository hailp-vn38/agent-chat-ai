import time
import wave
import os
from pathlib import Path
from app.core.logger import setup_logging
from typing import Optional, Tuple, List
from app.ai.providers.asr.dto.dto import InterfaceType
from app.ai.providers.asr.base import ASRProviderBase

import numpy as np
from chunkformer import ChunkFormerModel

TAG = __name__
logger = setup_logging()


class ASRProvider(ASRProviderBase):
    def __init__(self, config: dict, delete_audio_file: bool):
        super().__init__()
        self.interface_type = InterfaceType.LOCAL

        # Lấy output directory
        from app.ai.utils.paths import get_tmp_dir

        output_dir = config.get("output_dir")

        if not output_dir:
            output_dir = str(get_tmp_dir())
        else:
            output_dir = Path(output_dir).resolve()

        self.output_dir = str(output_dir)
        self.repo_id = config.get("repo_id", "khanhld/chunkformer-rnnt-large-vie")
        self.delete_audio_file = delete_audio_file

        # Model directory - nếu có sẽ load/download model vào đây thay vì ~/.cache
        model_dir = config.get("model_dir")
        if model_dir:
            from app.ai.utils.paths import get_models_data_dir

            self.model_dir = str(get_models_data_dir() / model_dir)
        else:
            self.model_dir = None

        # Chunkformer specific parameters
        self.chunk_size = config.get("chunk_size", 64)
        self.left_context_size = config.get("left_context_size", 128)
        self.right_context_size = config.get("right_context_size", 128)
        self.total_batch_duration = config.get("total_batch_duration", 1800)

        logger.bind(tag=TAG).debug(f"output_dir (absolute): {self.output_dir}")
        if self.model_dir:
            logger.bind(tag=TAG).debug(f"model_dir: {self.model_dir}")

        # đảm bảo output directory tồn tại
        os.makedirs(self.output_dir, exist_ok=True)

        # khởi tạo model
        try:
            model_path = self._get_model_path()
            logger.bind(tag=TAG).info(f"đang tải model từ {model_path}...")

            self.model = ChunkFormerModel.from_pretrained(model_path)

            logger.bind(tag=TAG).info("khởi tạo ChunkFormer ASR provider thành công!")

        except Exception as e:
            logger.bind(tag=TAG).error(f"lỗi khi tải model: {str(e)}")
            raise

    def _get_model_path(self) -> str:
        """
        Lấy đường dẫn model. Nếu model_dir được cấu hình:
        - Nếu đã có model local → trả về path local
        - Nếu chưa có → download từ HuggingFace Hub vào model_dir
        Nếu không có model_dir → trả về repo_id để load từ HuggingFace cache
        """
        if not self.model_dir:
            return self.repo_id

        # Kiểm tra xem model đã được download chưa
        model_file = Path(self.model_dir) / "pytorch_model.pt"
        if model_file.exists():
            logger.bind(tag=TAG).debug(f"sử dụng model local: {self.model_dir}")
            return self.model_dir

        # Download model từ HuggingFace Hub vào model_dir
        logger.bind(tag=TAG).info(
            f"downloading model từ {self.repo_id} vào {self.model_dir}..."
        )

        from huggingface_hub import snapshot_download

        snapshot_download(
            repo_id=self.repo_id,
            local_dir=self.model_dir,
            local_dir_use_symlinks=False,
        )

        logger.bind(tag=TAG).info(f"download hoàn tất: {self.model_dir}")
        return self.model_dir

    def read_wave(self, wave_filename: str) -> Tuple[np.ndarray, int]:
        """
        đọc file wave và trả về samples (float32) và sample rate.

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
        """chuyển đổi giọng nói thành text"""
        file_path = None
        try:
            # lưu audio file
            start_time = time.time()
            if audio_format == "pcm":
                pcm_data = opus_data
            else:
                pcm_data = self.decode_opus(opus_data)

            file_path = self.save_audio_to_file(pcm_data, session_id)
            logger.bind(tag=TAG).debug(
                f"lưu audio mất {time.time() - start_time:.3f}s | đường dẫn: {file_path}"
            )

            # nhận diện giọng nói bằng ChunkFormer
            start_time = time.time()

            # Sử dụng batch_decode với một file audio
            transcriptions = self.model.batch_decode(
                audio_paths=[file_path],
                chunk_size=self.chunk_size,
                left_context_size=self.left_context_size,
                right_context_size=self.right_context_size,
                total_batch_duration=self.total_batch_duration,
            )

            # Lấy kết quả đầu tiên
            text = transcriptions[0].lower() if transcriptions else ""

            logger.bind(tag=TAG).debug(
                f"nhận diện mất {time.time() - start_time:.3f}s | kết quả: {text}"
            )

            return text, file_path

        except Exception as e:
            logger.bind(tag=TAG).error(f"lỗi nhận diện giọng nói: {e}", exc_info=True)
            return "", file_path
        finally:
            # xóa file tạm nếu cần
            if self.delete_audio_file and file_path and os.path.exists(file_path):
                try:
                    os.remove(file_path)
                    logger.bind(tag=TAG).debug(f"đã xóa file tạm: {file_path}")
                except Exception as e:
                    logger.bind(tag=TAG).error(
                        f"không thể xóa file: {file_path} | lỗi: {e}"
                    )
