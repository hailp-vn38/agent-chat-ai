import os
import re
import uuid
import queue
import asyncio
import threading
import traceback
from app.ai.utils import p3
from datetime import datetime
from app.ai.utils import textUtils
from typing import Callable, Any
from abc import ABC, abstractmethod
from app.core.logger import setup_logging
from app.ai.utils.tts import MarkdownCleaner
# from app.ai.utils.output_counter import add_device_output
from app.ai.handle.reportHandle import enqueue_tts_report
from app.ai.handle.sendAudioHandle import sendAudioMessage
from app.ai.utils.util import audio_bytes_to_data_stream, audio_to_data_stream
from app.ai.providers.tts.dto.dto import (
    TTSMessageDTO,
    SentenceType,
    ContentType,
    InterfaceType,
)

TAG = __name__
logger = setup_logging()


class TTSProviderBase(ABC):
    def __init__(self, config, delete_audio_file):
        self.interface_type = InterfaceType.NON_STREAM
        self.conn = None
        self.delete_audio_file = delete_audio_file
        self.audio_file_type = "wav"
        self.output_file = config.get("output_dir", "tmp/")
        self.tts_text_queue = queue.Queue()
        self.tts_audio_queue = queue.Queue()
        self.tts_audio_first_sentence = True
        self.before_stop_play_files = []

        self.tts_text_buff = []
        self.punctuations = (
            "。",
            ".",
            "？",
            "?",
            "！",
            "!",
            "；",
            ";",
            "：",
            "…",
        )
        self.first_sentence_punctuations = (
            "，",
            "~",
            "、",
            ",",
            "。",
            ".",
            "？",
            "?",
            "！",
            "!",
            "；",
            ";",
            "：",
            "…",
        )
        self.tts_stop_request = False
        self.processed_chars = 0
        self.is_first_sentence = True

    def generate_filename(self, extension=".wav"):
        return os.path.join(
            self.output_file,
            f"tts-{datetime.now().date()}@{uuid.uuid4().hex}{extension}",
        )

    def _split_long_text(self, text: str, max_length: int = 200) -> list:
        """
        Tách text thành các segments nhỏ dựa trên:
        1. Dấu bullet (•) hoặc dấu gạch ngang (-)
        2. Giới hạn chiều dài max_length
        3. Context awareness (không tách số thập phân, ngoặc đơn)

        Args:
            text: Text cần tách
            max_length: Chiều dài tối đa của mỗi segment (default 200)

        Returns:
            List các segments đã tách
        """
        if not text or len(text) <= max_length:
            return [text] if text else []

        segments = []
        current_segment = ""

        i = 0
        while i < len(text):
            char = text[i]

            # Kiểm tra dấu bullet • hoặc dấu gạch ngang -
            if char in ("•", "-"):
                # Đối với dấu bullet, luôn tách thành segment riêng
                if char == "•":
                    if current_segment.strip():
                        segments.append(current_segment.strip())
                    current_segment = "•"
                    i += 1
                    # Thêm space sau bullet nếu có
                    if i < len(text) and text[i] == " ":
                        current_segment += " "
                        i += 1
                    continue

                # Đối với dấu gạch ngang, kiểm tra context
                # Bỏ qua nếu đó là phần của số thập phân (VD: 2023-11-03)
                is_decimal_or_date = False
                if i > 0 and i < len(text) - 1:
                    if text[i - 1].isdigit() and text[i + 1].isdigit():
                        is_decimal_or_date = True

                if not is_decimal_or_date:
                    if current_segment.strip():
                        segments.append(current_segment.strip())
                    current_segment = "-"
                    i += 1
                    if i < len(text) and text[i] == " ":
                        current_segment += " "
                        i += 1
                    continue

            # Thêm ký tự vào segment hiện tại
            current_segment += char

            # Nếu segment vượt quá max_length, tìm điểm tách an toàn
            if len(current_segment) >= max_length:
                # Tìm dấu câu gần nhất (hoặc space) để tách
                split_pos = max_length
                for j in range(max_length, max(0, max_length - 50), -1):
                    if current_segment[j] in (
                        "。",
                        ".",
                        "？",
                        "?",
                        "！",
                        "!",
                        "，",
                        ",",
                        " ",
                    ):
                        split_pos = j + 1
                        break

                segments.append(current_segment[:split_pos].strip())
                current_segment = current_segment[split_pos:].lstrip()

            i += 1

        # Thêm phần còn lại
        if current_segment.strip():
            segments.append(current_segment.strip())

        return segments

    def handle_opus(self, opus_data: bytes):
        # logger.bind(tag=TAG).debug(
        #     f"Đẩy số khung dữ liệu vào hàng đợi: {len(opus_data)}"
        # )
        self.tts_audio_queue.put((SentenceType.MIDDLE, opus_data, None))

    def handle_audio_file(self, file_audio: bytes, text):
        self.before_stop_play_files.append((file_audio, text))

    def to_tts_stream(self, text, opus_handler: Callable[[bytes], None] = None) -> None:
        text = MarkdownCleaner.clean_markdown(text)
        max_repeat_time = 5
        if self.delete_audio_file:
            # Khi cần xóa file, chuyển trực tiếp thành dữ liệu âm thanh
            while max_repeat_time > 0:
                try:
                    audio_bytes = asyncio.run(self.text_to_speak(text, None))
                    if audio_bytes:
                        self.tts_audio_queue.put((SentenceType.FIRST, None, text))
                        audio_bytes_to_data_stream(
                            audio_bytes,
                            file_type=self.audio_file_type,
                            is_opus=True,
                            callback=opus_handler,
                        )
                        break
                    else:
                        max_repeat_time -= 1
                except Exception as e:
                    logger.bind(tag=TAG).warning(
                        f"Tạo giọng nói thất bại {5 - max_repeat_time + 1} lần: {text}, lỗi: {e}"
                    )
                    max_repeat_time -= 1
            if max_repeat_time > 0:
                logger.bind(tag=TAG).debug(
                    f"Tạo giọng nói thành công: {text}, số lần thử lại: {5 - max_repeat_time}"
                )
            else:
                logger.bind(tag=TAG).error(
                    f"Tạo giọng nói thất bại: {text}, vui lòng kiểm tra mạng hoặc dịch vụ"
                )
            return None
        else:
            tmp_file = self.generate_filename()
            try:
                while not os.path.exists(tmp_file) and max_repeat_time > 0:
                    try:
                        asyncio.run(self.text_to_speak(text, tmp_file))
                    except Exception as e:
                        logger.bind(tag=TAG).warning(
                            f"Tạo giọng nói thất bại {5 - max_repeat_time + 1} lần: {text}, lỗi: {e}"
                        )
                        # Nếu chưa thành công, xóa file tạm
                        if os.path.exists(tmp_file):
                            os.remove(tmp_file)
                        max_repeat_time -= 1

                if max_repeat_time > 0:
                    logger.bind(tag=TAG).debug(
                        f"Tạo giọng nói thành công: {text}:{tmp_file}, số lần thử lại: {5 - max_repeat_time}"
                    )
                else:
                    logger.bind(tag=TAG).error(
                        f"Tạo giọng nói thất bại: {text}, vui lòng kiểm tra mạng hoặc dịch vụ"
                    )
                    self.tts_audio_queue.put((SentenceType.FIRST, None, text))
                self._process_audio_file_stream(tmp_file, callback=opus_handler)
            except Exception as e:
                logger.bind(tag=TAG).error(f"Failed to generate TTS file: {e}")
                return None

    def to_tts(self, text):
        text = MarkdownCleaner.clean_markdown(text)
        max_repeat_time = 5
        if self.delete_audio_file:
            # Khi cần xóa file, chuyển trực tiếp thành dữ liệu âm thanh
            while max_repeat_time > 0:
                try:
                    audio_bytes = asyncio.run(self.text_to_speak(text, None))
                    if audio_bytes:
                        audio_datas = []
                        audio_bytes_to_data_stream(
                            audio_bytes,
                            file_type=self.audio_file_type,
                            is_opus=True,
                            callback=lambda data: audio_datas.append(data),
                        )
                        return audio_datas
                    else:
                        max_repeat_time -= 1
                except Exception as e:
                    logger.bind(tag=TAG).warning(
                        f"Tạo giọng nói thất bại {5 - max_repeat_time + 1} lần: {text}, lỗi: {e}"
                    )
                    max_repeat_time -= 1
            if max_repeat_time > 0:
                logger.bind(tag=TAG).debug(
                    f"Tạo giọng nói thành công: {text}, số lần thử lại: {5 - max_repeat_time}"
                )
            else:
                logger.bind(tag=TAG).error(
                    f"Tạo giọng nói thất bại: {text}, vui lòng kiểm tra mạng hoặc dịch vụ"
                )
            return None
        else:
            tmp_file = self.generate_filename()
            try:
                while not os.path.exists(tmp_file) and max_repeat_time > 0:
                    try:
                        asyncio.run(self.text_to_speak(text, tmp_file))
                    except Exception as e:
                        logger.bind(tag=TAG).warning(
                            f"Tạo giọng nói thất bại {5 - max_repeat_time + 1} lần: {text}, lỗi: {e}"
                        )
                        # Nếu chưa thành công, xóa file tạm
                        if os.path.exists(tmp_file):
                            os.remove(tmp_file)
                        max_repeat_time -= 1

                if max_repeat_time > 0:
                    logger.bind(tag=TAG).debug(
                        f"Tạo giọng nói thành công: {text}:{tmp_file}, số lần thử lại: {5 - max_repeat_time}"
                    )
                else:
                    logger.bind(tag=TAG).error(
                        f"Tạo giọng nói thất bại: {text}, vui lòng kiểm tra mạng hoặc dịch vụ"
                    )

                return tmp_file
            except Exception as e:
                logger.bind(tag=TAG).error(f"Failed to generate TTS file: {e}")
                return None

    @abstractmethod
    async def text_to_speak(self, text, output_file):
        pass

    def audio_to_pcm_data_stream(
        self, audio_file_path, callback: Callable[[Any], Any] = None
    ):
        """Chuyển đổi file âm thanh sang mã hóa PCM"""
        return audio_to_data_stream(audio_file_path, is_opus=False, callback=callback)

    def audio_to_opus_data_stream(
        self, audio_file_path, callback: Callable[[Any], Any] = None
    ):
        """Chuyển đổi file âm thanh sang mã hóa Opus"""
        return audio_to_data_stream(audio_file_path, is_opus=True, callback=callback)

    def tts_one_sentence(
        self,
        conn,
        content_type,
        content_detail=None,
        content_file=None,
        sentence_id=None,
    ):
        """Gửi một câu thoại"""
        if not sentence_id:
            if conn.sentence_id:
                sentence_id = conn.sentence_id
            else:
                sentence_id = str(uuid.uuid4().hex)
                conn.sentence_id = sentence_id

        # Với câu đơn, tiến hành chia đoạn
        # Bước 1: Tách theo dấu bullet (•) và dấu gạch (-) với giới hạn 200 ký tự
        long_segments = self._split_long_text(content_detail, max_length=200)

        for long_seg in long_segments:
            # Bước 2: Áp dụng logic punctuation cũ cho mỗi long segment
            # Regex pattern: Tách các dấu câu nhưng không tách dấu . khi có chữ số trước
            segments = re.split(r"([。！？!?；;\n]|(?<!\d)\.)", long_seg)

            for seg in segments:
                self.tts_text_queue.put(
                    TTSMessageDTO(
                        sentence_id=sentence_id,
                        sentence_type=SentenceType.MIDDLE,
                        content_type=content_type,
                        content_detail=seg,
                        content_file=content_file,
                    )
                )

    async def open_audio_channels(self, conn):
        self.conn = conn
        # Luồng xử lý văn bản TTS
        self.tts_priority_thread = threading.Thread(
            target=self.tts_text_priority_thread, daemon=True
        )
        self.tts_priority_thread.start()

        # Luồng xử lý phát âm thanh
        self.audio_play_priority_thread = threading.Thread(
            target=self._audio_play_priority_thread, daemon=True
        )
        self.audio_play_priority_thread.start()

    # Mặc định xử lý không theo dạng streaming
    # Nếu cần streaming, hãy ghi đè trong lớp con
    def tts_text_priority_thread(self):
        while not self.conn.stop_event.is_set():
            try:
                message = self.tts_text_queue.get(timeout=1)
                if message.sentence_type == SentenceType.FIRST:
                    self.conn.client_abort = False
                if self.conn.client_abort:
                    logger.bind(tag=TAG).info(
                        "Nhận tín hiệu ngắt, dừng luồng xử lý văn bản TTS"
                    )
                    continue
                if message.sentence_type == SentenceType.FIRST:
                    # Khởi tạo lại các tham số
                    self.tts_stop_request = False
                    self.processed_chars = 0
                    self.tts_text_buff = []
                    self.is_first_sentence = True
                    self.tts_audio_first_sentence = True
                elif ContentType.TEXT == message.content_type:
                    self.tts_text_buff.append(message.content_detail)
                    segment_text = self._get_segment_text()
                    if segment_text:
                        self.to_tts_stream(segment_text, opus_handler=self.handle_opus)
                elif ContentType.FILE == message.content_type:
                    self._process_remaining_text_stream(opus_handler=self.handle_opus)
                    tts_file = message.content_file
                    if tts_file and os.path.exists(tts_file):
                        self._process_audio_file_stream(
                            tts_file, callback=self.handle_opus
                        )
                if message.sentence_type == SentenceType.LAST:
                    self._process_remaining_text_stream(opus_handler=self.handle_opus)
                    self.tts_audio_queue.put(
                        (message.sentence_type, [], message.content_detail)
                    )

            except queue.Empty:
                continue
            except Exception as e:
                logger.bind(tag=TAG).error(
                    f"Lỗi xử lý văn bản TTS: {str(e)}, loại: {type(e).__name__}, stack: {traceback.format_exc()}"
                )
                continue

    def _audio_play_priority_thread(self):
        # Danh sách văn bản và âm thanh cần báo cáo
        enqueue_text = None
        enqueue_audio = None
        while not self.conn.stop_event.is_set():
            text = None
            try:
                try:
                    sentence_type, audio_datas, text = self.tts_audio_queue.get(
                        timeout=0.1
                    )
                except queue.Empty:
                    if self.conn.stop_event.is_set():
                        break
                    continue

                if self.conn.client_abort:
                    logger.bind(tag=TAG).debug(
                        "Nhận tín hiệu ngắt, bỏ qua dữ liệu âm thanh hiện tại"
                    )
                    enqueue_text, enqueue_audio = None, []
                    continue

                # Khi nhận câu mới hoặc kết thúc phiên thì báo cáo
                if sentence_type is not SentenceType.MIDDLE:
                    # Báo cáo dữ liệu TTS
                    if enqueue_text is not None and enqueue_audio is not None:
                        enqueue_tts_report(self.conn, enqueue_text, enqueue_audio)
                    enqueue_audio = []
                    enqueue_text = text

                # Thu thập âm thanh để báo cáo
                if isinstance(audio_datas, bytes) and enqueue_audio is not None:
                    enqueue_audio.append(audio_datas)

                # Gửi âm thanh
                future = asyncio.run_coroutine_threadsafe(
                    sendAudioMessage(self.conn, sentence_type, audio_datas, text),
                    self.conn.loop,
                )
                future.result()

                # # Ghi lại lượng đầu ra
                # if self.conn.max_output_size > 0 and text:
                #     add_device_output(self.conn.headers.get("device-id"), len(text))

            except Exception as e:
                logger.bind(tag=TAG).error(f"audio_play_priority_thread: {text} {e}")

    async def start_session(self, session_id):
        pass

    async def finish_session(self, session_id):
        pass

    async def close(self):
        """Dọn dẹp tài nguyên"""
        if hasattr(self, "ws") and self.ws:
            await self.ws.close()

    def _get_segment_text(self):
        # Gộp toàn bộ văn bản hiện có và xử lý phần chưa tách
        full_text = "".join(self.tts_text_buff)
        current_text = full_text[self.processed_chars :]  # Bắt đầu từ phần chưa xử lý
        last_punct_pos = -1

        # Chọn bộ dấu câu tùy theo có phải câu đầu tiên hay không
        punctuations_to_use = (
            self.first_sentence_punctuations
            if self.is_first_sentence
            else self.punctuations
        )

        for idx, char in enumerate(current_text):
            if char in punctuations_to_use:
                # Kiểm tra xem dấu . có phải là số thập phân không
                if char == ".":
                    # Nếu dấu . có chữ số trước nó, bỏ qua (không phải kết thúc câu)
                    if idx > 0 and current_text[idx - 1].isdigit():
                        continue
                    # Nếu dấu . có chữ số sau nó, bỏ qua (số thập phân)
                    if idx < len(current_text) - 1 and current_text[idx + 1].isdigit():
                        continue
                last_punct_pos = idx

        if last_punct_pos != -1:
            segment_text_raw = current_text[: last_punct_pos + 1]
            segment_text = textUtils.get_string_no_punctuation_or_emoji(
                segment_text_raw,
                keep_trailing_punctuations=self.punctuations,
            )
            self.processed_chars += len(segment_text_raw)  # Cập nhật vị trí đã xử lý

            # Nếu là câu đầu tiên và đã gặp dấu phẩy, đặt lại cờ
            if self.is_first_sentence:
                self.is_first_sentence = False

            return segment_text
        elif self.tts_stop_request and current_text:
            segment_text = current_text
            self.is_first_sentence = True  # Đặt lại cờ
            return segment_text
        else:
            return None

    def _process_audio_file_stream(
        self, tts_file, callback: Callable[[Any], Any]
    ) -> None:
        """Xử lý file âm thanh và chuyển sang định dạng yêu cầu

        Args:
            tts_file: Đường dẫn file âm thanh
            callback: Hàm xử lý file
        """
        if tts_file.endswith(".p3"):
            p3.decode_opus_from_file_stream(tts_file, callback=callback)
        elif self.conn.audio_format == "pcm":
            self.audio_to_pcm_data_stream(tts_file, callback=callback)
        else:
            self.audio_to_opus_data_stream(tts_file, callback=callback)

        if (
            self.delete_audio_file
            and tts_file is not None
            and os.path.exists(tts_file)
            and tts_file.startswith(self.output_file)
        ):
            os.remove(tts_file)

    def _process_before_stop_play_files(self):
        for audio_datas, text in self.before_stop_play_files:
            self.tts_audio_queue.put((SentenceType.MIDDLE, audio_datas, text))
        self.before_stop_play_files.clear()
        self.tts_audio_queue.put((SentenceType.LAST, [], None))

    def _process_remaining_text_stream(
        self, opus_handler: Callable[[bytes], None] = None
    ):
        """Xử lý phần văn bản còn lại và sinh giọng nói

        Returns:
            bool: Đã xử lý được văn bản hay chưa
        """
        full_text = "".join(self.tts_text_buff)
        remaining_text = full_text[self.processed_chars :]
        if remaining_text:
            segment_text = textUtils.get_string_no_punctuation_or_emoji(remaining_text)
            if segment_text:
                self.to_tts_stream(segment_text, opus_handler=opus_handler)
                self.processed_chars += len(full_text)
                return True
        return False
