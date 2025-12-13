from __future__ import annotations

import time
import json
import asyncio
from typing import TYPE_CHECKING

from app.ai.utils.util import audio_to_data
from app.ai.handle.abortHandle import handleAbortMessage
from app.ai.handle.intentHandler import handle_user_intent
from app.ai.handle.sendAudioHandle import send_stt_message, SentenceType

if TYPE_CHECKING:
    from app.ai.connection import ConnectionHandler


TAG = __name__


async def handleAudioMessage(conn: ConnectionHandler, audio):
    # Đợi pipeline âm thanh sẵn sàng để không làm rơi khung âm thanh đầu tiên
    if not conn.components_ready.is_set():
        conn.logger.bind(tag=TAG).debug("Chờ pipeline âm thanh khởi tạo")
    await conn.components_ready.wait()

    if conn.vad is None or conn.asr is None:
        conn.logger.bind(tag=TAG).warning("Bỏ qua audio vì ASR/VAD chưa sẵn sàng")
        return

    # Kiểm tra đoạn hiện tại có giọng nói hay không
    have_voice = conn.vad.is_vad(conn, audio)
    # Nếu thiết bị vừa được đánh thức, tạm thời bỏ qua kiểm tra VAD
    if hasattr(conn, "just_woken_up") and conn.just_woken_up:
        have_voice = False
        # Thiết lập một khoảng trễ ngắn rồi khôi phục kiểm tra VAD
        conn.asr_audio.clear()
        if not hasattr(conn, "vad_resume_task") or conn.vad_resume_task.done():
            conn.vad_resume_task = asyncio.create_task(resume_vad_detection(conn))
        return
    # Ở chế độ manual không ngắt nội dung đang phát
    if have_voice:
        if conn.client_is_speaking and conn.client_listen_mode != "manual":
            await handleAbortMessage(conn)
    # Phát hiện thiết bị rảnh trong thời gian dài để nói lời tạm biệt
    await no_voice_close_connect(conn, have_voice)
    # Nhận dữ liệu âm thanh
    await conn.asr.receive_audio(conn, audio, have_voice)


async def resume_vad_detection(conn):
    # Chờ 2 giây rồi khôi phục kiểm tra VAD
    await asyncio.sleep(1)
    conn.just_woken_up = False


async def startToChat(conn: ConnectionHandler, text: str):
    # Đảm bảo pipeline âm thanh đã sẵn sàng trước khi gửi phản hồi tới client
    await conn.wait_for_pipeline_ready()

    # Kiểm tra xem đầu vào có ở định dạng JSON (bao gồm thông tin người nói) hay không
    speaker_name = None
    actual_text = text

    try:
        # Thử phân tích đầu vào ở định dạng JSON
        if text.strip().startswith("{") and text.strip().endswith("}"):
            data = json.loads(text)
            if "speaker" in data and "content" in data:
                speaker_name = data["speaker"]
                actual_text = data["content"]
                conn.logger.bind(tag=TAG).info(
                    f"Phân tích được thông tin người nói: {speaker_name}"
                )

                # Sử dụng nguyên văn bản ở định dạng JSON, không tách
                actual_text = text
    except (json.JSONDecodeError, KeyError):
        # Nếu phân tích thất bại, tiếp tục dùng văn bản gốc
        pass

    # Lưu thông tin người nói vào đối tượng kết nối
    if speaker_name:
        conn.current_speaker = speaker_name
    else:
        conn.current_speaker = None

    # # Nếu số lượng từ xuất ra trong ngày vượt quá giới hạn
    # if conn.max_output_size > 0:
    #     if check_device_output_limit(
    #         conn.headers.get("device-id"), conn.max_output_size
    #     ):
    #         await max_out_size(conn)
    #         return
    # Ở chế độ manual không ngắt nội dung đang phát
    if conn.client_is_speaking and conn.client_listen_mode != "manual":
        await handleAbortMessage(conn)

    # Trước tiên phân tích ý định với nội dung thực tế
    intent_handled = await handle_user_intent(conn, actual_text)

    if intent_handled:
        # Nếu ý định đã được xử lý thì không tiếp tục trò chuyện
        return

    # Nếu ý định chưa được xử lý, tiếp tục quy trình trò chuyện thông thường với nội dung thực tế
    await send_stt_message(conn, actual_text)
    conn.submit_blocking_task(conn.chat, actual_text)


async def no_voice_close_connect(conn: ConnectionHandler, have_voice: bool):
    if have_voice:
        conn.last_activity_time = time.time() * 1000
        return
    # Chỉ kiểm tra quá thời gian khi đã khởi tạo dấu thời gian
    if conn.last_activity_time > 0.0:
        no_voice_time = time.time() * 1000 - conn.last_activity_time
        close_connection_no_voice_time = int(
            conn.config.get("close_connection_no_voice_time", 120)
        )
        if (
            not conn.close_after_chat
            and no_voice_time > 1000 * close_connection_no_voice_time
        ):
            conn.close_after_chat = True
            conn.client_abort = False
            end_prompt = conn.config.get("end_prompt", {})
            if end_prompt and end_prompt.get("enable", True) is False:
                conn.logger.bind(tag=TAG).info(
                    "Kết thúc hội thoại, không cần gửi lời nhắc kết thúc"
                )
                await conn.close()
                return
            prompt = end_prompt.get("prompt")
            if not prompt:
                prompt = "Hãy mở đầu bằng ```thời gian trôi thật nhanh``` và kết thúc cuộc trò chuyện này bằng lời lẽ đầy cảm xúc, lưu luyến nhé!"
            await startToChat(conn, prompt)


async def max_out_size(conn: ConnectionHandler):
    # Phát thông báo vượt quá giới hạn số chữ
    conn.client_abort = False
    text = "Xin lỗi nhé, hiện giờ tôi bận một chút, chúng ta trò chuyện tiếp vào giờ này ngày mai nhé! Nhớ hẹn đấy, tạm biệt!"
    await send_stt_message(conn, text)
    file_path = "config/assets/max_output_size.wav"
    opus_packets = audio_to_data(file_path)
    conn.tts.tts_audio_queue.put((SentenceType.LAST, opus_packets, text))
    conn.close_after_chat = True
