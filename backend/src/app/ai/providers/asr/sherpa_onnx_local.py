import time
import wave
import os
import sys
import io
from pathlib import Path
from app.core.logger import setup_logging
from typing import Optional, Tuple, List
from app.ai.providers.asr.dto.dto import InterfaceType
from app.ai.providers.asr.base import ASRProviderBase

import numpy as np
import sherpa_onnx
from huggingface_hub import hf_hub_download

TAG = __name__
logger = setup_logging()


# Capture standard output
class CaptureOutput:
    def __enter__(self):
        self._output = io.StringIO()
        self._original_stdout = sys.stdout
        sys.stdout = self._output
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        sys.stdout = self._original_stdout
        self.output = self._output.getvalue()
        self._output.close()

        # output captured content via logger
        if self.output:
            logger.bind(tag=TAG).info(self.output.strip())


class ASRProvider(ASRProviderBase):
    def __init__(self, config: dict, delete_audio_file: bool):
        super().__init__()
        self.interface_type = InterfaceType.LOCAL

        # Lấy các thư mục từ path utilities
        from app.ai.utils.paths import get_models_data_dir, get_tmp_dir

        # convert relative paths to absolute paths
        model_dir = config.get("model_dir")
        output_dir = config.get("output_dir")

        if not model_dir:
            model_dir = str(get_models_data_dir() / "sherpa_onnx_local")
        else:
            model_dir = Path(model_dir).resolve()

        if not output_dir:
            output_dir = str(get_tmp_dir())
        else:
            output_dir = Path(output_dir).resolve()

        self.model_dir = str(model_dir)
        self.output_dir = str(output_dir)
        self.repo_id = config.get("repo_id", "hynt/Zipformer-30M-RNNT-6000h")
        self.delete_audio_file = delete_audio_file
        self.use_int8 = config.get("use_int8", True)  # mặc định dùng phiên bản int8

        # Phương án 1: Tối ưu độ chính xác - Tăng threads & Beam Search
        self.num_threads = config.get("num_threads", 8)  # Tăng từ 2 → 8
        self.decoding_method = config.get(
            "decoding_method", "beam_search"
        )  # Từ greedy → beam_search

        logger.bind(tag=TAG).debug(f"model_dir (absolute): {self.model_dir}")
        logger.bind(tag=TAG).debug(f"output_dir (absolute): {self.output_dir}")
        logger.bind(tag=TAG).debug(f"num_threads: {self.num_threads}")
        logger.bind(tag=TAG).debug(f"decoding_method: {self.decoding_method}")

        # đảm bảo output directory tồn tại
        os.makedirs(self.output_dir, exist_ok=True)
        os.makedirs(self.model_dir, exist_ok=True)

        # Cho phép override filename từ config, fallback default cho repo mặc định
        # Mỗi repo HuggingFace có thể có tên file khác nhau
        encoder_filename = config.get("encoder_filename")
        decoder_filename = config.get("decoder_filename")
        joiner_filename = config.get("joiner_filename")
        tokens_filename = config.get("tokens_filename", "config.json")

        # Default repo - chỉ dùng default filename cho repo này
        default_repo = "hynt/Zipformer-30M-RNNT-6000h"
        is_custom_repo = self.repo_id != default_repo

        # Validation: Nếu dùng custom repo, BẮT BUỘC phải có các filename config
        if is_custom_repo:
            missing_fields = []
            if not encoder_filename:
                missing_fields.append("encoder_filename")
            if not decoder_filename:
                missing_fields.append("decoder_filename")
            if not joiner_filename:
                missing_fields.append("joiner_filename")

            if missing_fields:
                raise ValueError(
                    f"Khi sử dụng custom repo_id '{self.repo_id}', "
                    f"bạn phải cung cấp các config: {', '.join(missing_fields)}. "
                    f"Mỗi repo HuggingFace có tên file model khác nhau."
                )

        # Nếu không có override, dùng default cho repo mặc định
        if not encoder_filename:
            encoder_filename = (
                "encoder-epoch-20-avg-10.int8.onnx"
                if self.use_int8
                else "encoder-epoch-20-avg-10.onnx"
            )
        if not decoder_filename:
            decoder_filename = "decoder-epoch-20-avg-10.onnx"
        if not joiner_filename:
            joiner_filename = (
                "joiner-epoch-20-avg-10.int8.onnx"
                if self.use_int8
                else "joiner-epoch-20-avg-10.onnx"
            )

        # tải các file model từ HuggingFace nếu chưa có
        try:
            logger.bind(tag=TAG).info(
                f"đang kiểm tra và tải model từ {self.repo_id}..."
            )

            self.encoder_path = self._download_model_file(encoder_filename)
            self.decoder_path = self._download_model_file(decoder_filename)
            self.joiner_path = self._download_model_file(joiner_filename)
            self.tokens_path = self._download_model_file(tokens_filename)

            logger.bind(tag=TAG).info("tất cả model files đã sẵn sàng.")

        except Exception as e:
            logger.bind(tag=TAG).error(f"lỗi khi tải model: {str(e)}")
            raise

        # khởi tạo recognizer với from_transducer
        with CaptureOutput():
            self.recognizer = sherpa_onnx.OfflineRecognizer.from_transducer(
                tokens=self.tokens_path,
                encoder=self.encoder_path,
                decoder=self.decoder_path,
                joiner=self.joiner_path,
                num_threads=self.num_threads,  # Tối ưu: 8 threads
                sample_rate=16000,
                feature_dim=80,
                decoding_method=self.decoding_method,  # Tối ưu: beam_search
            )

        logger.bind(tag=TAG).info("khởi tạo asr provider thành công!")

    def _download_model_file(self, filename: str) -> str:
        """tải file từ HuggingFace Hub nếu chưa tồn tại"""
        local_path = os.path.join(self.model_dir, filename)

        if not os.path.exists(local_path):
            logger.bind(tag=TAG).info(f"đang tải {filename}...")
            downloaded_path = hf_hub_download(
                repo_id=self.repo_id,
                filename=filename,
                cache_dir=self.model_dir,
                local_dir=self.model_dir,
                local_dir_use_symlinks=False,
            )
            logger.bind(tag=TAG).info(f"đã tải xong {filename}")
            return downloaded_path
        else:
            logger.bind(tag=TAG).debug(f"{filename} đã tồn tại, bỏ qua tải.")
            return local_path

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

            # nhận diện giọng nói
            start_time = time.time()
            stream = self.recognizer.create_stream()
            samples, sample_rate = self.read_wave(file_path)
            stream.accept_waveform(sample_rate, samples)
            self.recognizer.decode_stream(stream)
            text = stream.result.text.lower()  # convert to lowercase

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
