from __future__ import annotations
from typing import TYPE_CHECKING

import os
import io
import wave
import uuid
import json
import time
import queue
import asyncio
import traceback
import threading
import opuslib_next
import concurrent.futures
from abc import ABC, abstractmethod
from app.core.logger import setup_logging
from typing import Optional, Tuple, List
from app.ai.handle.receiveAudioHandle import startToChat
from app.ai.handle.reportHandle import enqueue_asr_report
from app.ai.utils.util import remove_punctuation_and_length
from app.ai.handle.receiveAudioHandle import handleAudioMessage

TAG = __name__
logger = setup_logging()

if TYPE_CHECKING:
    from app.ai.connection import ConnectionHandler  # chỉ dùng cho hint, không chạy lúc runtime



class ASRProviderBase(ABC):
    def __init__(self):
        pass

    # Mở kênh âm thanh
    async def open_audio_channels(self, conn: ConnectionHandler):
        conn.asr_priority_thread = threading.Thread(
            target=self.asr_text_priority_thread, args=(conn,), daemon=True
        )
        conn.asr_priority_thread.start()

    # Xử lý âm thanh ASR theo thứ tự
    def asr_text_priority_thread(self, conn: ConnectionHandler):
        while not conn.stop_event.is_set():
            try:
                message = conn.asr_audio_queue.get(timeout=1)
                future = asyncio.run_coroutine_threadsafe(
                    handleAudioMessage(conn, message),
                    conn.loop,
                )
                future.result()
            except queue.Empty:
                continue
            except Exception as e:
                logger.bind(tag=TAG).error(
                    f"Xử lý văn bản ASR thất bại: {str(e)}, loại: {type(e).__name__}, stack: {traceback.format_exc()}"
                )
                continue

    # Nhận âm thanh
    async def receive_audio(self, conn: ConnectionHandler, audio: bytes, audio_have_voice: bool):
        if conn.client_listen_mode == "auto" or conn.client_listen_mode == "realtime":
            have_voice = audio_have_voice
        else:
            have_voice = conn.client_have_voice
        
        conn.asr_audio.append(audio)
        if not have_voice and not conn.client_have_voice:
            conn.asr_audio = conn.asr_audio[-10:]
            return

        if conn.client_voice_stop:
            # Thu thập thêm các gói âm thanh còn tồn trong hàng đợi để tránh mất dữ liệu
            extra_packets = []
            while True:
                try:
                    extra_audio = conn.asr_audio_queue.get_nowait()
                except queue.Empty:
                    break
                else:
                    if extra_audio:
                        extra_packets.append(extra_audio)
            if extra_packets:
                conn.asr_audio.extend(extra_packets)

            asr_audio_task = conn.asr_audio.copy()
            conn.asr_audio.clear()
            conn.reset_vad_states()

            if len(asr_audio_task) > 15:
                await self.handle_voice_stop(conn, asr_audio_task)

    # Xử lý khi giọng nói dừng lại
    async def handle_voice_stop(self, conn: ConnectionHandler, asr_audio_task: List[bytes]):
        """Xử lý song song ASR và nhận dạng giọng nói"""
        try:
            total_start_time = time.monotonic()
            
            # Chuẩn bị dữ liệu âm thanh
            if conn.audio_format == "pcm":
                pcm_data = asr_audio_task
            else:
                pcm_data = self.decode_opus(asr_audio_task)
            
            combined_pcm_data = b"".join(pcm_data)
            
            # Chuẩn bị dữ liệu WAV trước
            wav_data = None
            if conn.voiceprint_provider and combined_pcm_data:
                wav_data = self._pcm_to_wav(combined_pcm_data)
            
            # Định nghĩa tác vụ ASR
            def run_asr():
                start_time = time.monotonic()
                try:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    try:
                        result = loop.run_until_complete(
                            self.speech_to_text(asr_audio_task, conn.session_id, conn.audio_format)
                        )
                        end_time = time.monotonic()
                        logger.bind(tag=TAG).info(f"Thời gian ASR: {end_time - start_time:.3f}s")
                        return result
                    finally:
                        loop.close()
                except Exception as e:
                    end_time = time.monotonic()
                    logger.bind(tag=TAG).error(f"ASR thất bại: {e}")
                    return ("", None)
            
            # Định nghĩa tác vụ nhận dạng giọng nói
            def run_voiceprint():
                if not wav_data:
                    return None
                try:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    try:
                        # Sử dụng nhà cung cấp nhận dạng giọng nói gắn với kết nối
                        result = loop.run_until_complete(
                            conn.voiceprint_provider.identify_speaker(wav_data, conn.session_id)
                        )
                        return result
                    finally:
                        loop.close()
                except Exception as e:
                    logger.bind(tag=TAG).error(f"Nhận dạng giọng nói thất bại: {e}")
                    return None
            
            # Chạy song song bằng ThreadPoolExecutor
            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as thread_executor:
                asr_future = thread_executor.submit(run_asr)
                
                if conn.voiceprint_provider and wav_data:
                    voiceprint_future = thread_executor.submit(run_voiceprint)
                    
                    # Chờ cả hai luồng hoàn thành
                    asr_result = asr_future.result(timeout=15)
                    voiceprint_result = voiceprint_future.result(timeout=15)
                    
                    results = {"asr": asr_result, "voiceprint": voiceprint_result}
                else:
                    asr_result = asr_future.result(timeout=15)
                    results = {"asr": asr_result, "voiceprint": None}
            
            
            # Xử lý kết quả
            raw_text, _ = results.get("asr", ("", None))
            speaker_name = results.get("voiceprint", None)
            
            # Ghi lại kết quả nhận dạng
            if raw_text:
                logger.bind(tag=TAG).info(f"Văn bản nhận dạng: {raw_text}")
            if speaker_name:
                logger.bind(tag=TAG).info(f"Người nói được nhận dạng: {speaker_name}")
            
            # Theo dõi hiệu năng
            total_time = time.monotonic() - total_start_time
            logger.bind(tag=TAG).info(f"Tổng thời gian xử lý: {total_time:.3f}s")
            
            # Kiểm tra độ dài văn bản
            text_len, _ = remove_punctuation_and_length(raw_text)
            self.stop_ws_connection()
            
            if text_len > 0:
                # Xây dựng chuỗi JSON kèm thông tin người nói
                enhanced_text = self._build_enhanced_text(raw_text, speaker_name)
                
                # Gửi báo cáo bằng mô-đun tùy chỉnh
                await startToChat(conn, enhanced_text)
                enqueue_asr_report(conn, enhanced_text, asr_audio_task)
                
        except Exception as e:
            logger.bind(tag=TAG).error(f"Xử lý dừng giọng nói thất bại: {e}")
            import traceback
            logger.bind(tag=TAG).debug(f"Chi tiết ngoại lệ: {traceback.format_exc()}")

    def _build_enhanced_text(self, text: str, speaker_name: Optional[str]) -> str:
        """Xây dựng văn bản có kèm thông tin người nói"""
        if speaker_name and speaker_name.strip():
            return json.dumps({
                "speaker": speaker_name,
                "content": text
            }, ensure_ascii=False)
        else:
            return text

    def _pcm_to_wav(self, pcm_data: bytes) -> bytes:
        """Chuyển đổi dữ liệu PCM sang định dạng WAV"""
        if len(pcm_data) == 0:
            logger.bind(tag=TAG).warning("Dữ liệu PCM trống, không thể chuyển sang WAV")
            return b""
        
        # Đảm bảo độ dài dữ liệu là số chẵn (âm thanh 16-bit)
        if len(pcm_data) % 2 != 0:
            pcm_data = pcm_data[:-1]
        
        # Tạo header tệp WAV
        wav_buffer = io.BytesIO()
        try:
            with wave.open(wav_buffer, 'wb') as wav_file:
                wav_file.setnchannels(1)      # Mono
                wav_file.setsampwidth(2)      # 16-bit
                wav_file.setframerate(16000)  # Tần số lấy mẫu 16 kHz
                wav_file.writeframes(pcm_data)
            
            wav_buffer.seek(0)
            wav_data = wav_buffer.read()
            
            return wav_data
        except Exception as e:
            logger.bind(tag=TAG).error(f"Chuyển đổi WAV thất bại: {e}")
            return b""

    def stop_ws_connection(self):
        pass

    def save_audio_to_file(self, pcm_data: List[bytes], session_id: str) -> str:
        """Lưu dữ liệu PCM thành tệp WAV"""
        module_name = __name__.split(".")[-1]
        file_name = f"asr_{module_name}_{session_id}_{uuid.uuid4()}.wav"
        file_path = os.path.join(self.output_dir, file_name)

        with wave.open(file_path, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)  # 2 bytes = 16-bit
            wf.setframerate(16000)
            wf.writeframes(b"".join(pcm_data))

        return file_path

    @abstractmethod
    async def speech_to_text(
        self, opus_data: List[bytes], session_id: str, audio_format="opus"
    ) -> Tuple[Optional[str], Optional[str]]:
        """Chuyển đổi dữ liệu giọng nói thành văn bản"""
        pass

    @staticmethod
    def decode_opus(opus_data: List[bytes]) -> List[bytes]:
        """Giải mã dữ liệu âm thanh Opus thành PCM"""
        try:
            decoder = opuslib_next.Decoder(16000, 1)
            pcm_data = []
            buffer_size = 960  # Mỗi lần xử lý 960 mẫu (60ms ở 16kHz)
            
            for i, opus_packet in enumerate(opus_data):
                try:
                    if not opus_packet or len(opus_packet) == 0:
                        continue
                    
                    pcm_frame = decoder.decode(opus_packet, buffer_size)
                    if pcm_frame and len(pcm_frame) > 0:
                        pcm_data.append(pcm_frame)
                        
                except opuslib_next.OpusError as e:
                    logger.bind(tag=TAG).warning(f"Lỗi giải mã Opus, bỏ qua gói dữ liệu {i}: {e}")
                except Exception as e:
                    logger.bind(tag=TAG).error(f"Lỗi xử lý âm thanh, gói dữ liệu {i}: {e}")
            
            return pcm_data
            
        except Exception as e:
            logger.bind(tag=TAG).error(f"Xảy ra lỗi trong quá trình giải mã âm thanh: {e}")
            return []
