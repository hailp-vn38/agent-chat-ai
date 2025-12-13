from __future__ import annotations
from typing import TYPE_CHECKING

import time
import json
import random
import asyncio
import copy
from app.ai.utils.dialogue import Message
from app.ai.utils.util import audio_to_data
from app.ai.providers.tts.dto.dto import SentenceType
from app.ai.utils.wakeup_word import WakeupWordsConfig
from app.ai.handle.sendAudioHandle import sendAudioMessage, send_tts_message
from app.ai.utils.util import remove_punctuation_and_length, opus_datas_to_wav_bytes
from app.ai.utils.paths import get_wakeup_words_short_audio

from app.ai.providers.tools.device_mcp import (
    MCPClient,
    send_mcp_initialize_message,
    send_mcp_tools_list_request,
)

if TYPE_CHECKING:
    from app.ai.connection import (
        ConnectionHandler,
    )  # chỉ dùng cho hint, không chạy lúc runtime


TAG = __name__

WAKEUP_CONFIG = {
    "refresh_time": 10,
    "responses": [
        "Tôi luôn ở đây, xin mời nói.",
        "Tôi đang sẵn sàng, cứ giao nhiệm vụ cho tôi bất cứ lúc nào.",
        "Tôi tới rồi, hãy cho tôi biết nhé.",
        "Xin mời nói, tôi đang lắng nghe.",
        "Xin hãy lên tiếng, tôi đã chuẩn bị xong.",
        "Vui lòng đưa ra chỉ dẫn nhé.",
        "Tôi đang chăm chú lắng nghe, xin mời.",
        "Bạn cần tôi hỗ trợ điều gì?",
        "Tôi ở đây và chờ chỉ dẫn của bạn.",
    ],
}

# Khởi tạo bộ quản lý cấu hình từ đánh thức dùng chung
wakeup_words_config = WakeupWordsConfig()

# Khóa dùng để tránh gọi wakeupWordsResponse đồng thời
_wakeup_response_lock = asyncio.Lock()


async def handleHelloMessage(conn: ConnectionHandler, msg_json):
    """Xử lý thông điệp hello"""
    # Bắt đầu với bản sao welcome_msg để tránh sửa trực tiếp config gốc
    response = copy.deepcopy(conn.welcome_msg) if conn.welcome_msg else {}

    response.setdefault("type", "hello")
    response.setdefault("status", "success")
    response["session_id"] = conn.session_id
    device_id = conn.get_device_id_for_json() or msg_json.get("device_id")
    if device_id:
        response["device_id"] = device_id

    audio_params = msg_json.get("audio_params")
    if audio_params:
        format = audio_params.get("format")
        conn.logger.bind(tag=TAG).debug(f"Định dạng âm thanh của client: {format}")
        conn.audio_format = format
        response.setdefault("audio_params", {})
        response["audio_params"].update(audio_params)
        frame_duration = audio_params.get("frame_duration")
        if isinstance(frame_duration, (int, float)) and frame_duration > 0:
            conn.gateway_frame_duration = int(frame_duration)
    features = msg_json.get("features")
    if features:
        conn.logger.bind(tag=TAG).debug(f"Tính năng của client: {features}")
        conn.features = features
        if features.get("mcp"):
            conn.logger.bind(tag=TAG).debug("Client hỗ trợ MCP")
            conn.mcp_client = MCPClient()
            # Gửi thông điệp khởi tạo
            asyncio.create_task(send_mcp_initialize_message(conn))
            # Gửi thông điệp MCP để lấy danh sách công cụ
            asyncio.create_task(send_mcp_tools_list_request(conn))

    conn.welcome_msg = response
    await conn.send_text(json.dumps(response))
    if not conn.components_ready.is_set():
        conn.logger.bind(tag=TAG).debug(
            "Pipeline âm thanh vẫn đang khởi tạo, vui lòng chờ trước khi gửi voice"
        )


async def checkWakeupWords(conn: ConnectionHandler, text: str):
    enable_wakeup_words_response_cache = conn.config[
        "enable_wakeup_words_response_cache"
    ]

    # Đảm bảo pipeline âm thanh sẵn sàng trước khi phản hồi wakeup
    await conn.wait_for_pipeline_ready()

    if not conn.tts:
        conn.logger.bind(tag=TAG).warning("TTS chưa sẵn sàng, bỏ qua phản hồi wakeup")
        return False

    if not enable_wakeup_words_response_cache:
        return False

    _, filtered_text = remove_punctuation_and_length(text)
    if filtered_text not in conn.config.get("wakeup_words"):
        return False

    conn.just_woken_up = True
    await send_tts_message(conn, "start")

    # Lấy giọng hiện tại
    voice = getattr(conn.tts, "voice", "default")
    if not voice:
        voice = "default"

    # Lấy cấu hình phản hồi từ đánh thức
    response = wakeup_words_config.get_wakeup_response(voice)
    if not response or not response.get("file_path"):
        response = {
            "voice": "default",
            "file_path": str(get_wakeup_words_short_audio()),
            "time": 0,
            "text": "Tôi đang ở đây nhé!",
        }

    # Lấy dữ liệu âm thanh
    opus_packets = audio_to_data(response.get("file_path"))
    # Phát phản hồi từ đánh thức
    conn.client_abort = False

    conn.logger.bind(tag=TAG).info(
        f"Phát phản hồi từ đánh thức: {response.get('text')}"
    )
    await sendAudioMessage(conn, SentenceType.FIRST, opus_packets, response.get("text"))
    await sendAudioMessage(conn, SentenceType.LAST, [], None)

    # Bổ sung hội thoại
    conn.dialogue.put(Message(role="assistant", content=response.get("text")))

    # Kiểm tra có cần cập nhật phản hồi từ đánh thức hay không
    if time.time() - response.get("time", 0) > WAKEUP_CONFIG["refresh_time"]:
        if not _wakeup_response_lock.locked():
            asyncio.create_task(wakeupWordsResponse(conn))
    return True


async def wakeupWordsResponse(conn: ConnectionHandler):
    if not conn.tts:
        return

    try:
        # Thử lấy khóa, nếu không được thì thoát
        if not await _wakeup_response_lock.acquire():
            return

        # Chọn ngẫu nhiên một câu trả lời trong danh sách có sẵn
        result = random.choice(WAKEUP_CONFIG["responses"])
        if not result or len(result) == 0:
            return

        # Tạo âm thanh TTS
        tts_result = await asyncio.to_thread(conn.tts.to_tts, result)
        if not tts_result:
            return

        # Lấy giọng hiện tại
        voice = getattr(conn.tts, "voice", "default")

        wav_bytes = opus_datas_to_wav_bytes(tts_result, sample_rate=16000)
        file_path = wakeup_words_config.generate_file_path(voice)
        with open(file_path, "wb") as f:
            f.write(wav_bytes)
        # Cập nhật cấu hình
        wakeup_words_config.update_wakeup_response(voice, file_path, result)
    finally:
        # Đảm bảo luôn giải phóng khóa trong mọi trường hợp
        if _wakeup_response_lock.locked():
            _wakeup_response_lock.release()
