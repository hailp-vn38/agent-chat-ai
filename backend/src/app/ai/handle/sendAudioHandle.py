from __future__ import annotations
import json
import time
import asyncio
import struct
from typing import TYPE_CHECKING
from app.ai.utils import textUtils
from app.ai.utils.util import audio_to_data
from app.ai.providers.tts.dto.dto import SentenceType

if TYPE_CHECKING:
    from app.ai.connection import (
        ConnectionHandler,
    )  # chỉ dùng cho hint, không chạy lúc runtime

TAG = __name__


async def sendAudioMessage(
    conn: ConnectionHandler, sentenceType: SentenceType, audios: bytes, text: str
):
    if conn.tts.tts_audio_first_sentence:
        conn.logger.bind(tag=TAG).debug(f"Gửi đoạn âm thanh đầu tiên: {text}")
        conn.tts.tts_audio_first_sentence = False
        await send_tts_message(conn, "start", None)

    if sentenceType == SentenceType.FIRST:
        await send_tts_message(conn, "sentence_start", text)

    await sendAudio(conn, audios)
    # Gửi thông điệp đánh dấu bắt đầu câu
    if sentenceType is not SentenceType.MIDDLE:
        conn.logger.bind(tag=TAG).debug(
            f"Gửi thông điệp âm thanh: {sentenceType}, {text}"
        )

    # Gửi thông điệp kết thúc (nếu đây là đoạn văn bản cuối cùng)
    if conn.llm_finish_task and sentenceType == SentenceType.LAST:
        await send_tts_message(conn, "stop", None)
        conn.client_is_speaking = False
        if conn.close_after_chat:
            await conn.close()


def calculate_timestamp_and_sequence(conn: ConnectionHandler, start_time, packet_index, frame_duration=60):
    """
    Tính toán timestamp và số thứ tự cho gói dữ liệu âm thanh
    Args:
        conn: Đối tượng kết nối
        start_time: Thời điểm bắt đầu (giá trị bộ đếm hiệu năng)
        packet_index: Chỉ số gói dữ liệu
        frame_duration: Thời lượng mỗi khung (ms), phù hợp với mã hóa Opus
    Returns:
        tuple: (timestamp, sequence)
    """
    # Tính toán timestamp dựa trên vị trí phát
    timestamp = int((start_time + packet_index * frame_duration / 1000) * 1000) % (
        2**32
    )

    # Tính toán số thứ tự
    if hasattr(conn, "audio_flow_control"):
        sequence = conn.audio_flow_control["sequence"]
    else:
        sequence = (
            packet_index  # Nếu không có trạng thái điều khiển luồng thì dùng chỉ số gốc
        )

    return timestamp, sequence


async def _send_to_mqtt_gateway(conn: ConnectionHandler, opus_packet, timestamp, sequence):
    """
    Gửi gói Opus kèm header 4 byte Binary Protocol V3 tới mqtt_gateway.
    Args:
        conn: Đối tượng kết nối
        opus_packet: Gói dữ liệu Opus
        timestamp: Timestamp (không truyền đi trong V3, giữ cho tương thích API)
        sequence: Số thứ tự gói (không dùng trong V3)
    """
    # Header V3: 4 bytes
    # [0] type, [1] reserved, [2-3] payload_size
    payload_len = len(opus_packet)
    if payload_len > 0xFFFF:
        raise ValueError("Kích thước khung Opus vượt quá giới hạn 65KB của Binary V3")

    header = struct.pack(">BBH", 0, 0, payload_len)

    complete_packet = header + opus_packet
    await conn.send_raw(complete_packet)


# Phát âm thanh
async def sendAudio(conn: ConnectionHandler, audios, frame_duration=60):
    """
    Gửi từng gói Opus, hỗ trợ điều khiển luồng
    Args:
        conn: Đối tượng kết nối
        opus_packet: Gói dữ liệu Opus đơn
        pre_buffer: Gửi nhanh phần âm thanh đệm
        frame_duration: Thời lượng mỗi khung (ms), phù hợp với Opus
    """
    if audios is None or len(audios) == 0:
        return

    if isinstance(audios, bytes):
        if conn.client_abort:
            return

        conn.last_activity_time = time.time() * 1000

        # Lấy hoặc khởi tạo trạng thái điều khiển luồng
        if not hasattr(conn, "audio_flow_control"):
            conn.audio_flow_control = {
                "last_send_time": 0,
                "packet_count": 0,
                "start_time": time.perf_counter(),
                "sequence": 0,  # Thêm số thứ tự
            }

        flow_control = conn.audio_flow_control
        current_time = time.perf_counter()
        # Tính thời điểm gửi dự kiến
        expected_time = flow_control["start_time"] + (
            flow_control["packet_count"] * frame_duration / 1000
        )
        delay = expected_time - current_time
        if delay > 0:
            await asyncio.sleep(delay)
        else:
            # Hiệu chỉnh sai lệch
            flow_control["start_time"] += abs(delay)

        if conn.conn_from_mqtt_gateway:
            # Tính timestamp và số thứ tự
            timestamp, sequence = calculate_timestamp_and_sequence(
                conn,
                flow_control["start_time"],
                flow_control["packet_count"],
                frame_duration,
            )
            # Gọi hàm dùng chung để gửi gói kèm header
            await _send_to_mqtt_gateway(conn, audios, timestamp, sequence)
        else:
            # Gửi trực tiếp gói Opus, không thêm header
            await conn.send_raw(audios)

        # Cập nhật trạng thái điều khiển luồng
        flow_control["packet_count"] += 1
        flow_control["sequence"] += 1
        flow_control["last_send_time"] = time.perf_counter()
    else:
        # Âm thanh dạng tệp sử dụng cách phát thông thường
        start_time = time.perf_counter()
        play_position = 0

        # Thực hiện đệm trước
        pre_buffer_frames = min(3, len(audios))
        for i in range(pre_buffer_frames):
            if conn.conn_from_mqtt_gateway:
                # Tính timestamp và số thứ tự
                timestamp, sequence = calculate_timestamp_and_sequence(
                    conn, start_time, i, frame_duration
                )
                # Gọi hàm dùng chung để gửi gói kèm header
                await _send_to_mqtt_gateway(conn, audios[i], timestamp, sequence)
            else:
                # Gửi trực tiếp gói đệm, không thêm header
                await conn.send_raw(audios[i])
        remaining_audios = audios[pre_buffer_frames:]

        # Phát các khung âm thanh còn lại
        for i, opus_packet in enumerate(remaining_audios):
            if conn.client_abort:
                break

            # Đặt lại trạng thái không có âm thanh
            conn.last_activity_time = time.time() * 1000

            # Tính thời điểm gửi dự kiến
            expected_time = start_time + (play_position / 1000)
            current_time = time.perf_counter()
            delay = expected_time - current_time
            if delay > 0:
                await asyncio.sleep(delay)

            if conn.conn_from_mqtt_gateway:
                # Tính timestamp và số thứ tự (sử dụng chỉ số gói hiện tại để đảm bảo liên tục)
                packet_index = pre_buffer_frames + i
                timestamp, sequence = calculate_timestamp_and_sequence(
                    conn, start_time, packet_index, frame_duration
                )
                # Gọi hàm dùng chung để gửi gói kèm header
                await _send_to_mqtt_gateway(conn, opus_packet, timestamp, sequence)
            else:
                # Gửi trực tiếp gói Opus, không thêm header
                await conn.send_raw(opus_packet)

            play_position += frame_duration


async def send_tts_message(conn: ConnectionHandler, state, text=None):
    """Gửi thông điệp trạng thái TTS"""
    if text is None and state == "sentence_start":
        return
    message = {"type": "tts", "state": state, "session_id": conn.session_id}
    if text is not None:
        message["text"] = textUtils.check_emoji(text)

    # Khi phát TTS kết thúc
    if state == "stop":
        # Phát âm báo
        tts_notify = conn.config.get("enable_stop_tts_notify", False)
        if tts_notify:
            stop_tts_notify_voice = conn.config.get(
                "stop_tts_notify_voice", "config/assets/tts_notify.mp3"
            )
            audios = audio_to_data(stop_tts_notify_voice, is_opus=True)
            await sendAudio(conn, audios)
        # Xóa trạng thái máy chủ đang nói
        conn.clearSpeakStatus()

    # Gửi thông điệp tới client
    await conn.send_raw(json.dumps(message))


async def send_stt_message(conn: ConnectionHandler, text: str):
    """Gửi thông điệp trạng thái STT"""
    end_prompt_str = conn.config.get("end_prompt", {}).get("prompt")
    if end_prompt_str and end_prompt_str == text:
        await send_tts_message(conn, "start")
        return

    # Phân tích định dạng JSON để trích xuất nội dung người dùng thực sự nói
    display_text = text
    try:
        # Thử phân tích định dạng JSON
        if text.strip().startswith("{") and text.strip().endswith("}"):
            parsed_data = json.loads(text)
            if isinstance(parsed_data, dict) and "content" in parsed_data:
                # Nếu là JSON có chứa thông tin người nói thì chỉ hiển thị phần content
                display_text = parsed_data["content"]
                # Lưu thông tin người nói vào đối tượng conn
                if "speaker" in parsed_data:
                    conn.current_speaker = parsed_data["speaker"]
    except (json.JSONDecodeError, TypeError):
        # Nếu không phải JSON thì dùng nguyên văn bản gốc
        display_text = text
    stt_text = textUtils.get_string_no_punctuation_or_emoji(display_text)
    await conn.send_raw(
        json.dumps({"type": "stt", "text": stt_text, "session_id": conn.session_id})
    )
    conn.client_is_speaking = True
    await send_tts_message(conn, "start")
