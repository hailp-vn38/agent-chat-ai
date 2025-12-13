import importlib
import os
import sys
from app.ai.providers.vad.base import VADProviderBase
from app.core.logger import setup_logging

# Thêm thư mục gốc dự án vào đường dẫn Python
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, "..", "..", ".."))
sys.path.insert(0, project_root)

TAG = __name__
logger = setup_logging()


def create_instance(class_name: str, *args, **kwargs) -> VADProviderBase:
    """Phương thức factory tạo instance VAD"""

    vad_path = os.path.join(
        project_root, "app", "ai", "providers", "vad", f"{class_name}.py"
    )

    if os.path.exists(vad_path):
        lib_name = f"app.ai.providers.vad.{class_name}"
        if lib_name not in sys.modules:
            sys.modules[lib_name] = importlib.import_module(lib_name)
        return sys.modules[lib_name].VADProvider(*args, **kwargs)

    raise ValueError(
        f"Loại VAD không được hỗ trợ: {class_name}, vui lòng kiểm tra cấu hình type. Đường dẫn: {vad_path}"
    )
