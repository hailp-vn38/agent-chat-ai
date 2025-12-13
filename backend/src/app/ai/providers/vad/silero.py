from __future__ import annotations
from typing import TYPE_CHECKING
import time
import numpy as np
import torch
import opuslib_next
from pathlib import Path

if TYPE_CHECKING:
    from app.ai.connection import (
        ConnectionHandler,
    )  # chỉ dùng cho hint, không chạy lúc runtime

from app.core.logger import setup_logging
from app.ai.providers.vad.base import VADProviderBase

TAG = __name__
logger = setup_logging()


class VADProvider(VADProviderBase):
    def __init__(self, config):
        logger.bind(tag=TAG).info("SileroVAD", config)

        # Lấy model_dir từ config, nếu không có thì dùng giá trị mặc định
        model_dir = config.get("model_dir")
        if not model_dir:
            # Lazy import để tránh circular dependency
            from app.ai.utils.paths import get_vad_models_dir

            model_dir = str(get_vad_models_dir() / "snakers4_silero-vad")

        # Chuyển đổi sang absolute path nếu là relative path
        model_dir = Path(model_dir).resolve()
        logger.bind(tag=TAG).debug(f"Model dir: {model_dir}")

        self.model, _ = torch.hub.load(
            repo_or_dir=str(model_dir),
            source="local",
            model="silero_vad",
            force_reload=False,
        )

        self.decoder = opuslib_next.Decoder(16000, 1)

        # Xử lý trường hợp chuỗi rỗng
        threshold = config.get("threshold", "0.5")
        threshold_low = config.get("threshold_low", "0.2")
        min_silence_duration_ms = config.get("min_silence_duration_ms", "1000")

        self.vad_threshold = float(threshold) if threshold else 0.5
        self.vad_threshold_low = float(threshold_low) if threshold_low else 0.2

        self.silence_threshold_ms = (
            int(min_silence_duration_ms) if min_silence_duration_ms else 1000
        )

        # Số khung tối thiểu để coi như có tiếng nói
        self.frame_window_threshold = 3

    def is_vad(self, conn: ConnectionHandler, opus_packet: bytes) -> bool:
        try:
            pcm_frame = self.decoder.decode(opus_packet, 960)
            conn.client_audio_buffer.extend(pcm_frame)  # Thêm dữ liệu mới vào bộ đệm

            # Xử lý khung đầy đủ trong bộ đệm (mỗi lần 512 mẫu)
            client_have_voice = False
            while len(conn.client_audio_buffer) >= 512 * 2:
                # Lấy 512 mẫu đầu tiên (1024 byte)
                chunk = conn.client_audio_buffer[: 512 * 2]
                conn.client_audio_buffer = conn.client_audio_buffer[512 * 2 :]

                # Chuyển sang định dạng tensor mà mô hình cần
                audio_int16 = np.frombuffer(chunk, dtype=np.int16)
                audio_float32 = audio_int16.astype(np.float32) / 32768.0
                audio_tensor = torch.from_numpy(audio_float32)

                # Phát hiện hoạt động giọng nói
                with torch.no_grad():
                    speech_prob = self.model(audio_tensor, 16000).item()

                # So sánh với hai ngưỡng
                if speech_prob >= self.vad_threshold:
                    is_voice = True
                elif speech_prob <= self.vad_threshold_low:
                    is_voice = False
                else:
                    is_voice = conn.last_is_voice

                # Nếu âm thanh chưa xuống dưới ngưỡng thấp nhất thì giữ trạng thái trước, coi như có tiếng nói
                conn.last_is_voice = is_voice

                # Cập nhật cửa sổ trượt
                conn.client_voice_window.append(is_voice)
                client_have_voice = (
                    conn.client_voice_window.count(True) >= self.frame_window_threshold
                )

                # Nếu trước đó có tiếng nói nhưng lần này không có, và thời gian im lặng đã vượt ngưỡng thì xem như đã nói xong một câu
                if conn.client_have_voice and not client_have_voice:
                    stop_duration = time.time() * 1000 - conn.last_activity_time
                    if stop_duration >= self.silence_threshold_ms:
                        conn.client_voice_stop = True
                if client_have_voice:
                    conn.client_have_voice = True
                    conn.last_activity_time = time.time() * 1000

            return client_have_voice
        except opuslib_next.OpusError as e:
            logger.bind(tag=TAG).info(f"Lỗi giải mã: {e}")
        except Exception as e:
            logger.bind(tag=TAG).error(f"Error processing audio packet: {e}")
