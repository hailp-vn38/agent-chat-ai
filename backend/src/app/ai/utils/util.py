import re
import os
import json
import copy
import wave
import socket
import requests
import subprocess
import numpy as np
from io import BytesIO
from . import p3
from pydub import AudioSegment
from typing import Callable, Any

TAG = __name__
emoji_map = {
    "neutral": "😶",
    "happy": "🙂",
    "laughing": "😆",
    "funny": "😂",
    "sad": "😔",
    "angry": "😠",
    "crying": "😭",
    "loving": "😍",
    "embarrassed": "😳",
    "surprised": "😲",
    "shocked": "😱",
    "thinking": "🤔",
    "winking": "😉",
    "cool": "😎",
    "relaxed": "😌",
    "delicious": "🤤",
    "kissy": "😘",
    "confident": "😏",
    "sleepy": "😴",
    "silly": "😜",
    "confused": "🙄",
}


def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # Connect to Google's DNS servers
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        return local_ip
    except Exception:
        return "127.0.0.1"


def is_private_ip(ip_addr):
    """
    Check if an IP address is a private IP address (compatible with IPv4 and IPv6).

    @param {string} ip_addr - The IP address to check.
    @return {bool} True if the IP address is private, False otherwise.
    """
    try:
        # Validate IPv4 or IPv6 address format
        if not re.match(
            r"^(\d{1,3}\.){3}\d{1,3}$|^([0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}$", ip_addr
        ):
            return False  # Invalid IP address format

        # IPv4 private address ranges
        if "." in ip_addr:  # IPv4 address
            ip_parts = list(map(int, ip_addr.split(".")))
            if ip_parts[0] == 10:
                return True  # 10.0.0.0/8 range
            elif ip_parts[0] == 172 and 16 <= ip_parts[1] <= 31:
                return True  # 172.16.0.0/12 range
            elif ip_parts[0] == 192 and ip_parts[1] == 168:
                return True  # 192.168.0.0/16 range
            elif ip_addr == "127.0.0.1":
                return True  # Loopback address
            elif ip_parts[0] == 169 and ip_parts[1] == 254:
                return True  # Link-local address 169.254.0.0/16
            else:
                return False  # Not a private IPv4 address
        else:  # IPv6 address
            ip_addr = ip_addr.lower()
            if ip_addr.startswith("fc00:") or ip_addr.startswith("fd00:"):
                return True  # Unique Local Addresses (FC00::/7)
            elif ip_addr == "::1":
                return True  # Loopback address
            elif ip_addr.startswith("fe80:"):
                return True  # Link-local unicast addresses (FE80::/10)
            else:
                return False  # Not a private IPv6 address

    except (ValueError, IndexError):
        return False  # IP address format error or insufficient segments


async def get_ip_info(ip_addr, logger):
    try:
        # Nhập trình quản lý bộ nhớ đệm toàn cục
        from .cache import async_cache_manager, CacheType

        cache_key = ip_addr or "unknown_ip"

        # Lấy từ bộ nhớ đệm trước
        cached_ip_info = await async_cache_manager.get(CacheType.IP_INFO, cache_key)
        if cached_ip_info is not None:
            return cached_ip_info

        # Nếu bộ nhớ đệm không có, gọi API
        if not ip_addr or is_private_ip(ip_addr):
            ip_info = {"city": "Vị trí chưa xác định"}
            await async_cache_manager.set(CacheType.IP_INFO, cache_key, ip_info)
            return ip_info

        url = f"https://whois.pconline.com.cn/ipJson.jsp?json=true&ip={ip_addr}"
        resp = requests.get(url, timeout=3)
        resp.raise_for_status()
        data = resp.json()
        ip_info = {"city": data.get("city", "Vị trí chưa xác định")}

        # Lưu vào bộ nhớ đệm
        await async_cache_manager.set(CacheType.IP_INFO, cache_key, ip_info)
        return ip_info
    except requests.RequestException as e:
        logger.bind(tag=TAG).error(f"Timeout khi lấy thông tin IP {ip_addr}: {e}")
        return {"city": "Vị trí chưa xác định"}
    except Exception as e:
        logger.bind(tag=TAG).error(f"Error getting client ip info: {e}")
        return {}


def write_json_file(file_path, data):
    """Ghi dữ liệu vào file JSON"""
    with open(file_path, "w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=4)


def remove_punctuation_and_length(text):
    # Phạm vi Unicode của ký tự full-width và half-width
    full_width_punctuations = (
        "！＂＃＄％＆＇（）＊＋，－。／：；＜＝＞？＠［＼］＾＿｀｛｜｝～"
    )
    half_width_punctuations = r'!"#$%&\'()*+,-./:;<=>?@[\]^_`{|}~'
    space = " "  # Khoảng trắng half-width
    full_width_space = "　"  # Khoảng trắng full-width

    # Loại bỏ ký tự full-width, half-width và khoảng trắng
    result = "".join(
        [
            char
            for char in text
            if char not in full_width_punctuations
            and char not in half_width_punctuations
            and char not in space
            and char not in full_width_space
        ]
    )

    if result == "Yeah":
        return 0, ""
    return len(result), result


def check_model_key(modelType, modelKey):
    if "你" in modelKey:
        return f"Lỗi cấu hình: API key của {modelType} chưa được thiết lập, giá trị hiện tại: {modelKey}"
    return None


def parse_string_to_list(value, separator=";"):
    """
    Chuyển giá trị đầu vào thành danh sách
    Args:
        value: Giá trị đầu vào, có thể là None, chuỗi hoặc danh sách
        separator: Ký tự phân tách, mặc định là dấu chấm phẩy
    Returns:
        list: Danh sách sau xử lý
    """
    if value is None or value == "":
        return []
    elif isinstance(value, str):
        return [item.strip() for item in value.split(separator) if item.strip()]
    elif isinstance(value, list):
        return value
    return []


def check_ffmpeg_installed():
    ffmpeg_installed = False
    try:
        # Chạy lệnh ffmpeg -version và thu kết quả
        result = subprocess.run(
            ["ffmpeg", "-version"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True,  # Ném lỗi nếu mã trả về khác 0
        )
        # Kiểm tra đầu ra có chứa thông tin phiên bản (tùy chọn)
        output = result.stdout + result.stderr
        if "ffmpeg version" in output.lower():
            ffmpeg_installed = True
        return False
    except (subprocess.CalledProcessError, FileNotFoundError):
        # Lệnh thực thi thất bại hoặc không tìm thấy
        ffmpeg_installed = False
    if not ffmpeg_installed:
        error_msg = "Máy tính của bạn chưa cài đặt ffmpeg đúng cách\n"
        error_msg += "\nKhuyến nghị:\n"
        error_msg += (
            "1. Làm theo tài liệu cài đặt của dự án để vào đúng môi trường conda\n"
        )
        error_msg += "2. Tham khảo tài liệu cài đặt để biết cách cài ffmpeg trong môi trường conda\n"
        raise ValueError(error_msg)


def extract_json_from_string(input_string):
    """Trích xuất phần JSON trong chuỗi"""
    pattern = r"(\{.*\})"
    match = re.search(pattern, input_string, re.DOTALL)  # Thêm re.DOTALL
    if match:
        return match.group(1)  # Trả về chuỗi JSON được trích xuất
    return None


def audio_to_data_stream(
    audio_file_path, is_opus=True, callback: Callable[[Any], Any] = None
) -> None:
    # Lấy phần mở rộng của tệp
    file_type = os.path.splitext(audio_file_path)[1]
    if file_type:
        file_type = file_type.lstrip(".")
    # Đọc tệp âm thanh; tham số -nostdin: không đọc từ stdin nếu không FFmpeg sẽ treo
    audio = AudioSegment.from_file(
        audio_file_path, format=file_type, parameters=["-nostdin"]
    )

    # Chuyển sang mono/tần số 16kHz/mã hóa little-endian 16-bit (đảm bảo khớp encoder)
    audio = audio.set_channels(1).set_frame_rate(16000).set_sample_width(2)

    # Lấy dữ liệu PCM gốc (16-bit little-endian)
    raw_data = audio.raw_data
    pcm_to_data_stream(raw_data, is_opus, callback)


def audio_to_data(audio_file_path: str, is_opus: bool = True) -> list[bytes]:
    """
    Chuyển tệp âm thanh thành danh sách khung mã hóa Opus/PCM
    Args:
        audio_file_path: Đường dẫn tệp âm thanh
        is_opus: Có mã hóa Opus hay không
    """
    import opuslib_next

    # Lấy phần mở rộng của tệp
    file_type = os.path.splitext(audio_file_path)[1]
    if file_type:
        file_type = file_type.lstrip(".")
    # Đọc tệp âm thanh; tham số -nostdin: không đọc từ stdin nếu không FFmpeg sẽ treo
    audio = AudioSegment.from_file(
        audio_file_path, format=file_type, parameters=["-nostdin"]
    )

    # Chuyển sang mono/tần số 16kHz/mã hóa little-endian 16-bit (đảm bảo khớp encoder)
    audio = audio.set_channels(1).set_frame_rate(16000).set_sample_width(2)

    # Lấy dữ liệu PCM gốc (16-bit little-endian)
    raw_data = audio.raw_data

    # Khởi tạo bộ mã hóa Opus
    encoder = opuslib_next.Encoder(16000, 1, opuslib_next.APPLICATION_AUDIO)

    # Tham số mã hóa
    frame_duration = 60  # 60ms per frame
    frame_size = int(16000 * frame_duration / 1000)  # 960 samples/frame

    datas = []
    # Xử lý dữ liệu âm thanh theo khung (bao gồm thêm số 0 ở cuối nếu thiếu)
    for i in range(0, len(raw_data), frame_size * 2):  # 16bit=2bytes/sample
        # Lấy dữ liệu nhị phân của khung hiện tại
        chunk = raw_data[i : i + frame_size * 2]

        # Nếu khung cuối không đủ dữ liệu thì chèn thêm số 0
        if len(chunk) < frame_size * 2:
            chunk += b"\x00" * (frame_size * 2 - len(chunk))

        if is_opus:
            # Chuyển sang mảng numpy để xử lý
            np_frame = np.frombuffer(chunk, dtype=np.int16)
            # Mã hóa dữ liệu Opus
            frame_data = encoder.encode(np_frame.tobytes(), frame_size)
        else:
            frame_data = chunk if isinstance(chunk, bytes) else bytes(chunk)

        datas.append(frame_data)

    return datas


def audio_bytes_to_data_stream(
    audio_bytes, file_type, is_opus, callback: Callable[[Any], Any]
) -> None:
    """
    Chuyển dữ liệu nhị phân âm thanh trực tiếp thành dữ liệu opus/pcm, hỗ trợ wav, mp3, p3
    """
    if file_type == "p3":
        # Giải mã trực tiếp bằng p3
        return p3.decode_opus_from_bytes_stream(audio_bytes, callback)
    else:
        # Định dạng khác sử dụng pydub
        audio = AudioSegment.from_file(
            BytesIO(audio_bytes), format=file_type, parameters=["-nostdin"]
        )
        audio = audio.set_channels(1).set_frame_rate(16000).set_sample_width(2)
        raw_data = audio.raw_data
        pcm_to_data_stream(raw_data, is_opus, callback)


def pcm_to_data_stream(raw_data, is_opus=True, callback: Callable[[Any], Any] = None):
    import opuslib_next

    # Khởi tạo bộ mã hóa Opus
    encoder = opuslib_next.Encoder(16000, 1, opuslib_next.APPLICATION_AUDIO)

    # Tham số mã hóa
    frame_duration = 60  # 60ms per frame
    frame_size = int(16000 * frame_duration / 1000)  # 960 samples/frame

    # Xử lý dữ liệu âm thanh theo từng khung (bao gồm thêm số 0 ở cuối nếu thiếu)
    for i in range(0, len(raw_data), frame_size * 2):  # 16bit=2bytes/sample
        # Lấy dữ liệu nhị phân của khung hiện tại
        chunk = raw_data[i : i + frame_size * 2]

        # Nếu khung cuối không đủ dữ liệu thì chèn thêm số 0
        if len(chunk) < frame_size * 2:
            chunk += b"\x00" * (frame_size * 2 - len(chunk))

        if is_opus:
            # Chuyển sang mảng numpy để xử lý
            np_frame = np.frombuffer(chunk, dtype=np.int16)
            # Mã hóa dữ liệu Opus
            frame_data = encoder.encode(np_frame.tobytes(), frame_size)
            callback(frame_data)
        else:
            frame_data = chunk if isinstance(chunk, bytes) else bytes(chunk)
            callback(frame_data)


def opus_datas_to_wav_bytes(opus_datas, sample_rate=16000, channels=1):
    """
    Giải mã danh sách khung opus thành luồng byte wav
    """
    import opuslib_next

    decoder = opuslib_next.Decoder(sample_rate, channels)
    pcm_datas = []

    frame_duration = 60  # ms
    frame_size = int(sample_rate * frame_duration / 1000)  # 960

    for opus_frame in opus_datas:
        # Giải mã thành PCM (trả về bytes, 2 byte mỗi mẫu)
        pcm = decoder.decode(opus_frame, frame_size)
        pcm_datas.append(pcm)

    pcm_bytes = b"".join(pcm_datas)

    # Ghi vào luồng byte wav
    wav_buffer = BytesIO()
    with wave.open(wav_buffer, "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(2)  # 16bit
        wf.setframerate(sample_rate)
        wf.writeframes(pcm_bytes)
    return wav_buffer.getvalue()


def check_vad_update(before_config, new_config):
    if (
        new_config.get("selected_module") is None
        or new_config["selected_module"].get("VAD") is None
    ):
        return False
    update_vad = False
    current_vad_module = before_config["selected_module"]["VAD"]
    new_vad_module = new_config["selected_module"]["VAD"]
    current_vad_type = (
        current_vad_module
        if "type" not in before_config["VAD"][current_vad_module]
        else before_config["VAD"][current_vad_module]["type"]
    )
    new_vad_type = (
        new_vad_module
        if "type" not in new_config["VAD"][new_vad_module]
        else new_config["VAD"][new_vad_module]["type"]
    )
    update_vad = current_vad_type != new_vad_type
    return update_vad


def check_asr_update(before_config, new_config):
    if (
        new_config.get("selected_module") is None
        or new_config["selected_module"].get("ASR") is None
    ):
        return False
    update_asr = False
    current_asr_module = before_config["selected_module"]["ASR"]
    new_asr_module = new_config["selected_module"]["ASR"]
    current_asr_type = (
        current_asr_module
        if "type" not in before_config["ASR"][current_asr_module]
        else before_config["ASR"][current_asr_module]["type"]
    )
    new_asr_type = (
        new_asr_module
        if "type" not in new_config["ASR"][new_asr_module]
        else new_config["ASR"][new_asr_module]["type"]
    )
    update_asr = current_asr_type != new_asr_type
    return update_asr


def filter_sensitive_info(config: dict) -> dict:
    """
    Lọc bỏ thông tin nhạy cảm trong cấu hình
    Args:
        config: Từ điển cấu hình gốc
    Returns:
        Từ điển cấu hình sau lọc
    """
    sensitive_keys = [
        "api_key",
        "personal_access_token",
        "access_token",
        "token",
        "secret",
        "access_key_secret",
        "secret_key",
    ]

    def _filter_dict(d: dict) -> dict:
        filtered = {}
        for k, v in d.items():
            if any(sensitive in k.lower() for sensitive in sensitive_keys):
                filtered[k] = "***"
            elif isinstance(v, dict):
                filtered[k] = _filter_dict(v)
            elif isinstance(v, list):
                filtered[k] = [_filter_dict(i) if isinstance(i, dict) else i for i in v]
            else:
                filtered[k] = v
        return filtered

    return _filter_dict(copy.deepcopy(config))


def get_vision_url(config: dict) -> str:
    """Lấy URL vision

    Args:
        config: Từ điển cấu hình

    Returns:
        str: URL vision
    """
    server_config = config["server"]
    vision_explain = server_config.get("vision_explain", "")
    if vision_explain == "" or vision_explain == "null":
        local_ip = get_local_ip()
        port = int(server_config.get("http_port", 8003))
        vision_explain = f"http://{local_ip}:{port}/api/v1/vision/explain"
    return vision_explain


def is_valid_image_file(file_data: bytes) -> bool:
    """
    Kiểm tra dữ liệu tệp có phải định dạng ảnh hợp lệ hay không

    Args:
        file_data: Dữ liệu nhị phân của tệp

    Returns:
        bool: Trả về True nếu là định dạng ảnh hợp lệ, nếu không trả về False
    """
    # Magic number (header) của các định dạng ảnh phổ biến
    image_signatures = {
        b"\xff\xd8\xff": "JPEG",
        b"\x89PNG\r\n\x1a\n": "PNG",
        b"GIF87a": "GIF",
        b"GIF89a": "GIF",
        b"BM": "BMP",
        b"II*\x00": "TIFF",
        b"MM\x00*": "TIFF",
        b"RIFF": "WEBP",
    }

    # Kiểm tra xem header có khớp với định dạng ảnh đã biết hay không
    for signature in image_signatures:
        if file_data.startswith(signature):
            return True

    return False


def sanitize_tool_name(name: str) -> str:
    """Sanitize tool names for OpenAI compatibility."""
    # Hỗ trợ ký tự tiếng Trung, chữ cái, số, gạch dưới và gạch nối
    return re.sub(r"[^a-zA-Z0-9_\-\u4e00-\u9fff]", "_", name)


def validate_mcp_endpoint(mcp_endpoint: str) -> bool:
    """
    Kiểm tra định dạng điểm kết nối MCP

    Args:
        mcp_endpoint: Chuỗi điểm kết nối MCP

    Returns:
        bool: Có hợp lệ hay không
    """
    # 1. Kiểm tra có bắt đầu bằng ws hay không
    if not mcp_endpoint.startswith("ws"):
        return False

    # 2. Kiểm tra có chứa từ key hoặc call hay không
    if "key" in mcp_endpoint.lower() or "call" in mcp_endpoint.lower():
        return False

    # 3. Kiểm tra có chứa chuỗi /mcp/ hay không
    if "/mcp/" not in mcp_endpoint:
        return False

    return True
