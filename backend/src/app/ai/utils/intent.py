import os
import sys
import importlib
from app.core.logger import setup_logging
from app.ai.utils.paths import get_ai_dir


logger = setup_logging()


def create_instance(class_name, *args, **kwargs):
    # Tạo instance intent
    # Đường dẫn trong fastapi-server-v2: xiaozhi_server/core/providers/intent
    intent_path = os.path.join(
        get_ai_dir(),
        "providers",
        "intent",
        class_name,
        f"{class_name}.py",
    )

    if os.path.exists(intent_path):
        lib_name = f"app.ai.providers.intent.{class_name}.{class_name}"
        if lib_name not in sys.modules:
            sys.modules[lib_name] = importlib.import_module(lib_name)
        return sys.modules[lib_name].IntentProvider(*args, **kwargs)

    raise ValueError(
        f"Loại intent không được hỗ trợ: {class_name}, vui lòng kiểm tra cấu hình type. Đường dẫn: {intent_path}"
    )
