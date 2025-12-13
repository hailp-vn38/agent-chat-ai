"""
Path Utilities - Lấy các đường dẫn cố định trong ứng dụng
Tất cả các đường dẫn được tính toán từ app root để tránh hard-code

Tổng hợp tất cả các path utility thay vì dùng Path(__file__).resolve().parents[n]
"""

from pathlib import Path
from typing import Union


def get_app_root() -> Path:
    """
    Lấy thư mục gốc của ứng dụng (main/fastapi-server-v2/app)

    Returns:
        Path: Thư mục gốc của app
    """
    return Path(__file__).resolve().parents[2]


def get_project_root() -> Path:
    """
    Lấy thư mục gốc của project (main/fastapi-server-v2)

    Returns:
        Path: Thư mục gốc của project
    """
    return Path(__file__).resolve().parents[3]


def get_config_dir() -> Path:
    """
    Lấy thư mục config (app/config)

    Returns:
        Path: Thư mục config
    """
    return get_app_root() / "config"


def get_data_dir() -> Path:
    """
    Lấy thư mục data (app/data)

    Returns:
        Path: Thư mục data
    """
    return get_app_root() / "data"


def get_ai_dir() -> Path:
    """
    Lấy thư mục AI (app/ai)

    Returns:
        Path: Thư mục AI
    """
    return get_app_root() / "ai"


def get_ai_config_dir() -> Path:
    """
    Lấy thư mục config của AI (app/ai/config)

    Returns:
        Path: Thư mục AI config
    """
    return get_ai_dir() / "config"


def get_base_config_file() -> Path:
    """
    Lấy đường dẫn file base config (app/ai/config/config.yml)
    Đây là default config ship cùng code.

    Returns:
        Path: Đường dẫn file base config
    """
    return get_ai_config_dir() / "config.yml"


def get_assets_dir() -> Path:
    """
    Lấy thư mục assets (app/config/assets)

    Returns:
        Path: Thư mục assets
    """
    return get_config_dir() / "assets"


def get_models_data_dir() -> Path:
    """
    Lấy thư mục models_data (src/app/data/model)

    Returns:
        Path: Thư mục models_data
    """
    models_dir = get_data_dir() / "model"
    models_dir.mkdir(parents=True, exist_ok=True)
    return models_dir


def get_vad_models_dir() -> Path:
    """
    Lấy thư mục VAD models (src/app/ai/model)

    Returns:
        Path: Thư mục VAD models
    """
    models_dir = get_ai_dir() / "model"
    models_dir.mkdir(parents=True, exist_ok=True)
    return models_dir


def get_wakeup_words_dir() -> Path:
    """
    Lấy thư mục wakeup words (app/config/assets/wakeup_words)

    Returns:
        Path: Thư mục wakeup words
    """
    return get_assets_dir() / "wakeup_words"


def get_wakeup_words_config_file() -> Path:
    """
    Lấy đường dẫn file cấu hình wakeup words (app/data/.wakeup_words.yaml)

    Returns:
        Path: Đường dẫn file cấu hình
    """
    return get_data_dir() / ".wakeup_words.yaml"


def get_music_dir() -> Path:
    """
    Lấy thư mục music (app/music)

    Returns:
        Path: Thư mục music
    """
    return get_app_root() / "music"


def get_performance_tester_dir() -> Path:
    """
    Lấy thư mục performance_tester (app/performance_tester)

    Returns:
        Path: Thư mục performance_tester
    """
    return get_app_root() / "performance_tester"


def get_plugins_func_dir() -> Path:
    """
    Lấy thư mục plugins_func (app/plugins_func)

    Returns:
        Path: Thư mục plugins_func
    """
    return get_ai_dir() / "plugins_func"


def get_tmp_dir() -> Path:
    """
    Lấy thư mục tmp (app/tmp)

    Returns:
        Path: Thư mục tmp
    """
    return get_app_root() / "tmp"


def get_wakeup_words_short_audio() -> Path:
    """
    Lấy đường dẫn file audio short wakeup (app/config/assets/wakeup_words_short.wav)

    Returns:
        Path: Đường dẫn file audio
    """
    return get_assets_dir() / "wakeup_words_short.wav"


def get_agent_base_prompt_file() -> Path:
    """
    Lấy đường dẫn file prompt cơ bản (app/ai/agent-base-prompt.txt)
    Sử dụng cho prompt_manager, intent, và các LLM providers

    Returns:
        Path: Đường dẫn file agent-base-prompt.txt
    """
    return get_ai_dir() / "agent-base-prompt.txt"


def get_mcp_server_settings_file() -> Path:
    """
    Lấy đường dẫn file cấu hình MCP server (app/data/mcp_server_settings.json)

    Returns:
        Path: Đường dẫn file mcp_server_settings.json
    """
    return get_data_dir() / "mcp_server_settings.json"


def get_config_file() -> Path:
    """
    Lấy đường dẫn file config mặc định (app/data/.config.yml)

    Returns:
        Path: Đường dẫn file config
    """
    return get_data_dir() / ".config.yml"


def get_src_dir() -> Path:
    """
    Lấy thư mục src (src)

    Returns:
        Path: Thư mục src
    """
    return get_project_root() / "src"


def get_logs_dir() -> Path:
    """
    Lấy thư mục logs (src/logs)

    Returns:
        Path: Thư mục logs
    """
    return get_src_dir() / "logs"


def ensure_dir_exists(path: Union[str, Path]) -> Path:
    """
    Đảm bảo thư mục tồn tại, tạo nếu chưa có

    Args:
        path: Đường dẫn thư mục

    Returns:
        Path: Đường dẫn thư mục đã được tạo
    """
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)
    return path


def ensure_file_dir_exists(file_path: Union[str, Path]) -> Path:
    """
    Đảm bảo thư mục chứa file tồn tại, tạo nếu chưa có

    Args:
        file_path: Đường dẫn file

    Returns:
        Path: Đường dẫn file
    """
    file_path = Path(file_path)
    ensure_dir_exists(file_path.parent)
    return file_path


def get_current_dir(file_path: str) -> Path:
    """
    Lấy thư mục chứa file (thay thế cho os.path.dirname(os.path.abspath(__file__)))

    Args:
        file_path: __file__ của module gọi function này

    Returns:
        Path: Thư mục chứa file
    """
    return Path(file_path).resolve().parent


def get_parent_dir(file_path: str, levels: int = 1) -> Path:
    """
    Lấy thư mục cha cách n level (thay thế cho os.path.dirname(os.path.dirname(__file__)))

    Args:
        file_path: __file__ của module gọi function này
        levels: Số level lên

    Returns:
        Path: Thư mục cha
    """
    return Path(file_path).resolve().parents[levels - 1]
