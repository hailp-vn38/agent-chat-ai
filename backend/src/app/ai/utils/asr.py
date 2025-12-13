import importlib
import os
import sys
from app.ai.providers.asr.base import ASRProviderBase
from app.core.logger import get_logger
from app.ai.utils.paths import get_ai_dir



TAG = __name__
logger = get_logger(TAG)


def create_instance(class_name: str, *args, **kwargs) -> ASRProviderBase:
    """Phương thức factory tạo instance ASR"""
    asr_path = os.path.join(
        get_ai_dir(), "providers", "asr", f"{class_name}.py"
    )

    if os.path.exists(asr_path):
        lib_name = f"app.ai.providers.asr.{class_name}"
        if lib_name not in sys.modules:
            sys.modules[lib_name] = importlib.import_module(lib_name)
        return sys.modules[lib_name].ASRProvider(*args, **kwargs)

    raise ValueError(
        f"Loại ASR không được hỗ trợ: {class_name}, vui lòng kiểm tra cấu hình type. Đường dẫn: {asr_path}"
    )
