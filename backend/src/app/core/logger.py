import sys
from pathlib import Path

from loguru import logger

from app.config.config_loader import load_config
from app.ai.utils.paths import get_app_root

SERVER_VERSION = "0.1.0"
_logger_initialized = False


def get_module_abbreviation(module_name, module_dict):
    """Lấy viết tắt của tên mô-đun, nếu rỗng trả về 00.
    Nếu tên có dấu gạch dưới, lấy hai ký tự đầu sau dấu gạch dưới cuối cùng.
    """
    module_value = module_dict.get(module_name, "")
    if not module_value:
        return "00"
    if "_" in module_value:
        parts = module_value.split("_")
        return parts[-1][:2] if parts[-1] else "00"
    return module_value[:2]


def build_module_string(selected_module):
    """Tạo chuỗi mô-đun ghép từ các thành phần đã chọn"""
    return (
        get_module_abbreviation("VAD", selected_module)
        + get_module_abbreviation("ASR", selected_module)
        + get_module_abbreviation("LLM", selected_module)
        + get_module_abbreviation("TTS", selected_module)
        + get_module_abbreviation("Memory", selected_module)
        + get_module_abbreviation("Intent", selected_module)
        + get_module_abbreviation("VLLM", selected_module)
    )


def formatter(record):
    """Bổ sung tag mặc định cho log và xử lý chuỗi mô-đun động"""
    record["extra"].setdefault("tag", record["name"])
    # Nếu chưa thiết lập selected_module thì dùng giá trị mặc định
    record["extra"].setdefault("selected_module", "00000000000000")
    # Đưa selected_module từ extra lên cấp cao nhất để hỗ trợ định dạng {selected_module}
    record["selected_module"] = record["extra"]["selected_module"]
    return record["message"]


def setup_logging():
    """Thiết lập logging với loguru"""
    config = load_config()
    log_config = config.get("log", {})
    global _logger_initialized

    # Chỉ cấu hình log khi khởi tạo lần đầu
    if not _logger_initialized:
        # Khởi tạo với chuỗi mô-đun mặc định
        logger.configure(
            extra={
                "selected_module": log_config.get("selected_module", "00000000000000"),
            }
        )

        log_format = log_config.get(
            "log_format",
            "<green>{time:YYMMDD HH:mm:ss}</green>[{version}_{extra[selected_module]}][<light-blue>{extra[tag]}</light-blue>]-<level>{level}</level>-<light-green>{message}</light-green>",
        )
        log_format_file = log_config.get(
            "log_format_file",
            "{time:YYYY-MM-DD HH:mm:ss} - {version}_{extra[selected_module]} - {name} - {level} - {extra[tag]} - {message}",
        )
        log_format = log_format.replace("{version}", SERVER_VERSION)
        log_format_file = log_format_file.replace("{version}", SERVER_VERSION)

        log_level = log_config.get("log_level", "INFO")
        base_dir = Path(__file__).resolve().parents[2]

        log_dir = Path(log_config.get("log_dir", "logs"))
        if not log_dir.is_absolute():
            log_dir = base_dir / log_dir
        log_file = log_config.get("log_file", "app.log")
        app_root = get_app_root()
        data_dir_value = log_config.get("data_dir")
        if data_dir_value:
            data_dir = Path(data_dir_value)
            if not data_dir.is_absolute():
                data_dir = app_root / data_dir
        else:
            data_dir = app_root / "data"

        try:
            log_dir.mkdir(parents=True, exist_ok=True)
        except PermissionError:
            # Fallback to /tmp if logs directory is not writable
            log_dir = Path("/tmp/logs")
            log_dir.mkdir(parents=True, exist_ok=True)

        try:
            data_dir.mkdir(parents=True, exist_ok=True)
        except PermissionError:
            # Fallback to /tmp if data directory is not writable
            pass

        # Cấu hình đầu ra logging
        logger.remove()

        # Ghi log ra console
        logger.add(sys.stdout, format=log_format, level=log_level, filter=formatter)

        # Ghi log ra file - chung thư mục, xoay vòng theo kích thước
        log_file_path = log_dir / log_file

        # Thêm handler ghi log
        logger.add(
            log_file_path,
            format=log_format_file,
            level=log_level,
            filter=formatter,
            rotation="10 MB",  # Mỗi file tối đa 10MB
            retention="30 days",  # Giữ lại 30 ngày
            compression=None,
            encoding="utf-8",
            enqueue=True,  # Đảm bảo an toàn bất đồng bộ
            backtrace=True,
            diagnose=True,
        )
        _logger_initialized = True  # Đánh dấu đã khởi tạo

    return logger


def create_connection_logger(selected_module_str):
    """Tạo logger riêng cho kết nối và gắn chuỗi mô-đun cụ thể"""
    return logger.bind(selected_module=selected_module_str)


def get_logger(module_name: str = None):
    """Lấy logger instance. Sử dụng: logger.bind(tag=__name__)"""
    if not _logger_initialized:
        setup_logging()

    if module_name:
        return logger.bind(tag=module_name)
    return logger
