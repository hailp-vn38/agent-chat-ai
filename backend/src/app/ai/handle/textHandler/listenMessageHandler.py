from __future__ import annotations
import time
from typing import Dict, Any,TYPE_CHECKING
from app.ai.handle.receiveAudioHandle import handleAudioMessage, startToChat
from app.ai.handle.reportHandle import enqueue_asr_report
from app.ai.handle.sendAudioHandle import send_stt_message, send_tts_message
from app.ai.handle.textMessageHandler import TextMessageHandler
from app.ai.handle.textMessageType import TextMessageType
from app.ai.utils.util import remove_punctuation_and_length

if TYPE_CHECKING:
    from app.ai.connection import ConnectionHandler  # chỉ dùng cho hint, không chạy lúc runtime


TAG = __name__


class ListenTextMessageHandler(TextMessageHandler):
    """Trình xử lý thông điệp Listen"""

    @property
    def message_type(self) -> TextMessageType:
        return TextMessageType.LISTEN

    async def handle(self, conn:ConnectionHandler , msg_json: Dict[str, Any]) -> None:
        if "mode" in msg_json:
            conn.client_listen_mode = msg_json["mode"]
            conn.logger.bind(tag=TAG).debug(
                f"Chế độ thu âm của client: {conn.client_listen_mode}"
            )
        state = msg_json["state"]
        if state == "start":
            conn.client_have_voice = True
            conn.client_voice_stop = False
        elif state == "stop":
            conn.client_have_voice = True
            conn.client_voice_stop = True
            if len(conn.asr_audio) > 0:
                await handleAudioMessage(conn, b"")
        elif state == "detect":
            conn.client_have_voice = False
            conn.asr_audio.clear()
            if "text" in msg_json:
                conn.last_activity_time = time.time() * 1000
                original_text = msg_json["text"]  # Giữ nguyên văn bản gốc
                filtered_len, filtered_text = remove_punctuation_and_length(
                    original_text
                )

                # Kiểm tra có phải từ đánh thức hay không
                is_wakeup_words = filtered_text in conn.config.get("wakeup_words")
                # Kiểm tra cấu hình trả lời khi có từ đánh thức
                enable_greeting = conn.config.get("enable_greeting", True)

                if is_wakeup_words and not enable_greeting:
                    # Nếu là từ đánh thức và tắt phản hồi từ đánh thức thì không cần trả lời
                    await send_stt_message(conn, original_text)
                    await send_tts_message(conn, "stop", None)
                    conn.client_is_speaking = False
                elif is_wakeup_words:
                    conn.just_woken_up = True
                    # Báo cáo dữ liệu văn bản thuần (tái sử dụng chức năng báo cáo ASR nhưng không gửi âm thanh)
                    enqueue_asr_report(conn, "Này, xin chào nhé", [])
                    await startToChat(conn, "Này, xin chào nhé")
                else:
                    # Báo cáo dữ liệu văn bản thuần (tái sử dụng chức năng báo cáo ASR nhưng không gửi âm thanh)
                    enqueue_asr_report(conn, original_text, [])
                    # Ngược lại cần LLM trả lời nội dung văn bản
                    await startToChat(conn, original_text)
