"""
Chức năng báo cáo TTS đã được tích hợp vào lớp ConnectionHandler.

Các khả năng báo cáo bao gồm:
1. Mỗi kết nối có hàng đợi và luồng xử lý báo cáo riêng.
2. Vòng đời của luồng báo cáo được gắn với đối tượng kết nối.
3. Sử dụng phương thức ConnectionHandler.enqueue_tts_report để thực hiện báo cáo.

Vui lòng tham khảo phần mã liên quan trong core/connection.py để biết chi tiết.
"""

from __future__ import annotations
import asyncio
import time
from typing import TYPE_CHECKING
import opuslib_next


if TYPE_CHECKING:
    from app.ai.connection import (
        ConnectionHandler,
    )  # chỉ dùng cho hint, không chạy lúc runtime

TAG = __name__


async def manage_report(
    agent_id: str,
    session_id: str,
    chat_type: int,
    content: str,
) -> bool:
    """Lưu message vào DB thông qua AgentService.

    Args:
        agent_id: Agent UUID
        session_id: Session UUID
        chat_type: 1 = user, 2 = assistant
        content: Text content

    Returns:
        bool: True nếu lưu thành công
    """
    from app.core.db.database import local_session
    from app.services.agent_service import agent_service

    try:
        async with local_session() as db:
            result = await agent_service.save_chat_message(
                db=db,
                agent_id=agent_id,
                session_id=session_id,
                chat_type=chat_type,
                content=content,
            )
            return result
    except Exception as e:
        # Log error but don't raise - report is non-critical
        import logging
        logging.getLogger(TAG).error(f"manage_report failed: {e}")
        return False


def report(
    conn: ConnectionHandler, type: int, text: str, opus_data: bytes, report_time: float
):
    """Thực hiện thao tác báo cáo nhật ký trò chuyện

    Args:
        conn: Đối tượng kết nối
        type: Kiểu báo cáo, 1 là người dùng, 2 là trợ lý
        text: Văn bản tổng hợp
        opus_data: Dữ liệu âm thanh Opus (bỏ qua, chỉ lưu text)
        report_time: Thời điểm báo cáo
    """
    try:
        # Bỏ qua audio, chỉ lưu text
        if not text or not text.strip():
            return

        # Cần agent_id để lưu message
        if not conn.agent_id:
            conn.logger.bind(tag=TAG).debug(
                "Bỏ qua báo cáo: không có agent_id"
            )
            return

        # Schedule async manage_report vào event loop
        if hasattr(conn, "loop") and conn.loop and conn.loop.is_running():
            asyncio.run_coroutine_threadsafe(
                manage_report(
                    agent_id=conn.agent_id,
                    session_id=conn.session_id,
                    chat_type=type,
                    content=text.strip(),
                ),
                conn.loop,
            )
            conn.logger.bind(tag=TAG).debug(
                f"Đã lên lịch lưu message: agent={conn.agent_id}, type={type}"
            )
        else:
            conn.logger.bind(tag=TAG).warning(
                "Không thể lưu message: event loop không khả dụng"
            )

    except Exception as e:
        conn.logger.bind(tag=TAG).error(f"Báo cáo nhật ký trò chuyện thất bại: {e}")


def opus_to_wav(conn: ConnectionHandler, opus_data: bytes):
    """Chuyển đổi dữ liệu Opus thành luồng byte định dạng WAV

    Args:
        output_dir: Tham số đầu ra (giữ lại để tương thích giao diện)
        opus_data: Dữ liệu âm thanh Opus

    Returns:
        bytes: Dữ liệu âm thanh ở định dạng WAV
    """
    decoder = opuslib_next.Decoder(16000, 1)  # 16kHz, âm thanh mono
    pcm_data = []

    for opus_packet in opus_data:
        try:
            pcm_frame = decoder.decode(opus_packet, 960)  # 960 samples = 60ms
            pcm_data.append(pcm_frame)
        except opuslib_next.OpusError as e:
            conn.logger.bind(tag=TAG).error(f"Lỗi giải mã Opus: {e}", exc_info=True)

    if not pcm_data:
        raise ValueError("Không có dữ liệu PCM hợp lệ")

    # Tạo header WAV
    pcm_data_bytes = b"".join(pcm_data)
    num_samples = len(pcm_data_bytes) // 2  # 16-bit samples

    # Header WAV
    wav_header = bytearray()
    wav_header.extend(b"RIFF")  # ChunkID
    wav_header.extend((36 + len(pcm_data_bytes)).to_bytes(4, "little"))  # ChunkSize
    wav_header.extend(b"WAVE")  # Format
    wav_header.extend(b"fmt ")  # Subchunk1ID
    wav_header.extend((16).to_bytes(4, "little"))  # Subchunk1Size
    wav_header.extend((1).to_bytes(2, "little"))  # AudioFormat (PCM)
    wav_header.extend((1).to_bytes(2, "little"))  # NumChannels
    wav_header.extend((16000).to_bytes(4, "little"))  # SampleRate
    wav_header.extend((32000).to_bytes(4, "little"))  # ByteRate
    wav_header.extend((2).to_bytes(2, "little"))  # BlockAlign
    wav_header.extend((16).to_bytes(2, "little"))  # BitsPerSample
    wav_header.extend(b"data")  # Subchunk2ID
    wav_header.extend(len(pcm_data_bytes).to_bytes(4, "little"))  # Subchunk2Size

    # Trả về toàn bộ dữ liệu WAV
    return bytes(wav_header) + pcm_data_bytes


def enqueue_tts_report(conn: ConnectionHandler, text: str, opus_data: bytes):
    """Đưa dữ liệu TTS vào hàng đợi báo cáo

    Args:
        conn: Đối tượng kết nối
        text: Văn bản tổng hợp
        opus_data: Dữ liệu âm thanh Opus
    """
    if not conn.read_config_from_api or not conn.report_tts_enable:
        return
    if conn.chat_history_conf == 0:
        return
    try:
        # Sử dụng hàng đợi của kết nối, truyền văn bản và dữ liệu nhị phân thay vì đường dẫn tệp
        if conn.chat_history_conf == 2:
            conn.report_queue.put((2, text, opus_data, int(time.time())))
            conn.logger.bind(tag=TAG).debug(
                f"Dữ liệu TTS đã được đưa vào hàng đợi báo cáo: {conn.device_id}, kích thước âm thanh: {len(opus_data)} "
            )
        else:
            conn.report_queue.put((2, text, None, int(time.time())))
            conn.logger.bind(tag=TAG).debug(
                f"Dữ liệu TTS đã được đưa vào hàng đợi báo cáo: {conn.device_id}, không báo cáo âm thanh"
            )
    except Exception as e:
        conn.logger.bind(tag=TAG).error(
            f"Thêm dữ liệu TTS vào hàng đợi báo cáo thất bại: {text}, {e}"
        )


def enqueue_asr_report(conn: ConnectionHandler, text: str, opus_data: bytes):
    """Đưa dữ liệu ASR vào hàng đợi báo cáo

    Args:
        conn: Đối tượng kết nối
        text: Văn bản tổng hợp
        opus_data: Dữ liệu âm thanh Opus
    """
    if not conn.read_config_from_api or not conn.report_asr_enable:
        return
    if conn.chat_history_conf == 0:
        return
    try:
        # Sử dụng hàng đợi của kết nối, truyền văn bản và dữ liệu nhị phân thay vì đường dẫn tệp
        if conn.chat_history_conf == 2:
            conn.report_queue.put((1, text, opus_data, int(time.time())))
            conn.logger.bind(tag=TAG).debug(
                f"Dữ liệu ASR đã được đưa vào hàng đợi báo cáo: {conn.device_id}, kích thước âm thanh: {len(opus_data)} "
            )
        else:
            conn.report_queue.put((1, text, None, int(time.time())))
            conn.logger.bind(tag=TAG).debug(
                f"Dữ liệu ASR đã được đưa vào hàng đợi báo cáo: {conn.device_id}, không báo cáo âm thanh"
            )
    except Exception as e:
        conn.logger.bind(tag=TAG).debug(
            f"Thêm dữ liệu ASR vào hàng đợi báo cáo thất bại: {text}, {e}"
        )
