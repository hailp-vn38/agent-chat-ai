from __future__ import annotations
from typing import TYPE_CHECKING
import json
import uuid
import asyncio
from app.ai.utils.dialogue import Message
from app.ai.providers.tts.dto.dto import ContentType
from app.ai.handle.helloHandle import checkWakeupWords
from app.ai.plugins_func.register import Action, ActionResponse
from app.ai.handle.sendAudioHandle import send_stt_message
from app.ai.utils.util import remove_punctuation_and_length
from app.ai.providers.tts.dto.dto import TTSMessageDTO, SentenceType

if TYPE_CHECKING:
    from app.ai.connection import ConnectionHandler  # chỉ dùng cho hint, không chạy lúc runtime


TAG = __name__


async def handle_user_intent(conn: ConnectionHandler, text: str):
    # Tiền xử lý văn bản đầu vào, xử lý khả năng ở định dạng JSON
    try:
        if text.strip().startswith("{") and text.strip().endswith("}"):
            parsed_data = json.loads(text)
            if isinstance(parsed_data, dict) and "content" in parsed_data:
                text = parsed_data["content"]  # Trích xuất content để phân tích ý định
                conn.current_speaker = parsed_data.get(
                    "speaker"
                )  # Giữ lại thông tin người nói
    except (json.JSONDecodeError, TypeError):
        pass

    # Kiểm tra xem có lệnh thoát rõ ràng hay không
    _, filtered_text = remove_punctuation_and_length(text)
    if await check_direct_exit(conn, text):
        return True

    # Kiểm tra xem có phải từ đánh thức hay không
    if await checkWakeupWords(conn, filtered_text):
        return True

    if conn.intent_type == "function_call":
        # Sử dụng phương thức trò chuyện hỗ trợ function calling, không phân tích ý định nữa
        return False
    # Dùng LLM để phân tích ý định
    intent_result = await analyze_intent_with_llm(conn, text)
    if not intent_result:
        return False
    # Khởi tạo sentence_id khi bắt đầu phiên
    conn.sentence_id = str(uuid.uuid4().hex)
    # Xử lý các loại ý định
    return await process_intent_result(conn, intent_result, text)


async def check_direct_exit(conn: ConnectionHandler, text: str):
    """Kiểm tra xem có lệnh thoát rõ ràng hay không"""
    _, normalized_text = remove_punctuation_and_length(text)
    normalized_text = normalized_text.lower()
    if not normalized_text:
        return False

    for cmd in getattr(conn, "cmd_exit", []):
        _, normalized_cmd = remove_punctuation_and_length(cmd)
        normalized_cmd = normalized_cmd.lower()
        if not normalized_cmd:
            continue
        if normalized_text == normalized_cmd:
            conn.logger.bind(tag=TAG).info(f"Phát hiện lệnh thoát rõ ràng: {text}")
            await send_stt_message(conn, text)
            conn.close_after_chat = True
            conn.client_abort = False
            conn.submit_blocking_task(conn.chat, text)
            return True
    return False


async def analyze_intent_with_llm(conn: ConnectionHandler, text: str):
    """Dùng LLM để phân tích ý định của người dùng"""
    if not hasattr(conn, "intent") or not conn.intent:
        conn.logger.bind(tag=TAG).warning("Dịch vụ nhận dạng ý định chưa được khởi tạo")
        return None

    # Lịch sử hội thoại
    dialogue = conn.dialogue
    try:
        intent_result = await conn.intent.detect_intent(conn, dialogue.dialogue, text)
        return intent_result
    except Exception as e:
        conn.logger.bind(tag=TAG).error(f"Nhận dạng ý định thất bại: {str(e)}")

    return None


async def process_intent_result(conn: ConnectionHandler, intent_result, original_text: str):
    """Xử lý kết quả nhận dạng ý định"""
    try:
        # Cố gắng phân tích kết quả thành JSON
        intent_data = json.loads(intent_result)

        # Kiểm tra xem có function_call hay không
        if "function_call" in intent_data:
            # Nhận function_call trực tiếp từ kết quả nhận dạng ý định
            conn.logger.bind(tag=TAG).debug(
                f"Phát hiện kết quả ý định dạng function_call: {intent_data['function_call']['name']}"
            )
            function_name = intent_data["function_call"]["name"]
            if function_name == "continue_chat":
                return False

            if function_name == "result_for_context":
                await send_stt_message(conn, original_text)
                conn.client_abort = False

                def process_context_result():
                    conn.dialogue.put(Message(role="user", content=original_text))

                    from app.ai.utils.current_time import get_current_time_info

                    current_time, today_date, today_weekday = (
                        get_current_time_info()
                    )

                    # Xây dựng gợi ý cơ bản kèm theo ngữ cảnh
                    context_prompt = f"""Thời gian hiện tại: {current_time}
                                        Ngày hôm nay: {today_date} ({today_weekday})
                                        Vui lòng dựa trên thông tin trên để trả lời câu hỏi của người dùng: {original_text}"""

                    response = conn.intent.replyResult(context_prompt, original_text)
                    speak_txt(conn, response)

                conn.submit_blocking_task(process_context_result)
                return True

            function_args = {}
            if "arguments" in intent_data["function_call"]:
                function_args = intent_data["function_call"]["arguments"]
                if function_args is None:
                    function_args = {}
            # Đảm bảo tham số là chuỗi JSON
            if isinstance(function_args, dict):
                function_args = json.dumps(function_args)

            function_call_data = {
                "name": function_name,
                "id": str(uuid.uuid4().hex),
                "arguments": function_args,
            }

            await send_stt_message(conn, original_text)
            conn.client_abort = False

            # Sử dụng executor để thực thi lời gọi hàm và xử lý kết quả
            def process_function_call():
                conn.dialogue.put(Message(role="user", content=original_text))

                # Sử dụng bộ xử lý công cụ thống nhất để xử lý mọi lời gọi công cụ
                try:
                    result = asyncio.run_coroutine_threadsafe(
                        conn.func_handler.handle_llm_function_call(
                            conn, function_call_data
                        ),
                        conn.loop,
                    ).result()
                except Exception as e:
                    conn.logger.bind(tag=TAG).error(f"Gọi công cụ thất bại: {e}")
                    result = ActionResponse(
                        action=Action.ERROR, result=str(e), response=str(e)
                    )

                if result:
                    if (
                        result.action == Action.RESPONSE
                    ):  # Phản hồi trực tiếp tới phía client
                        text = result.response
                        if text is not None:
                            speak_txt(conn, text)
                    elif (
                        result.action == Action.REQLLM
                    ):  # Sau khi gọi hàm thì yêu cầu LLM tạo câu trả lời
                        text = result.result
                        conn.dialogue.put(Message(role="tool", content=text))
                        llm_result = conn.intent.replyResult(text, original_text)
                        if llm_result is None:
                            llm_result = text
                        speak_txt(conn, llm_result)
                    elif (
                        result.action == Action.NOTFOUND
                        or result.action == Action.ERROR
                    ):
                        text = result.result
                        if text is not None:
                            speak_txt(conn, text)
                    elif function_name != "play_music":
                        # For backward compatibility with original code
                        # Lấy chỉ số văn bản mới nhất
                        text = result.response
                        if text is None:
                            text = result.result
                        if text is not None:
                            speak_txt(conn, text)

            # Đưa việc thực thi hàm vào thread pool
            conn.submit_blocking_task(process_function_call)
            return True
        return False
    except json.JSONDecodeError as e:
        conn.logger.bind(tag=TAG).error(f"Lỗi khi xử lý kết quả ý định: {e}")
        return False


def speak_txt(conn: ConnectionHandler, text: str):
    conn.tts.tts_text_queue.put(
        TTSMessageDTO(
            sentence_id=conn.sentence_id,
            sentence_type=SentenceType.FIRST,
            content_type=ContentType.ACTION,
        )
    )
    conn.tts.tts_one_sentence(conn, ContentType.TEXT, content_detail=text)
    conn.tts.tts_text_queue.put(
        TTSMessageDTO(
            sentence_id=conn.sentence_id,
            sentence_type=SentenceType.LAST,
            content_type=ContentType.ACTION,
        )
    )
    conn.dialogue.put(Message(role="assistant", content=text))
