import os
import sys
import importlib
from app.core.logger import setup_logging

from app.ai.utils.paths import get_ai_dir


logger = setup_logging()


def create_instance(class_name, *args, **kwargs):
    # Đường dẫn trong fastapi-server-v2: xiaozhi_server/core/providers/memory
    memory_path = os.path.join(
        get_ai_dir(),
        "providers",
        "memory",
        class_name,
        f"{class_name}.py",
    )

    if os.path.exists(memory_path):
        lib_name = f"app.ai.providers.memory.{class_name}.{class_name}"
        if lib_name not in sys.modules:
            sys.modules[lib_name] = importlib.import_module(lib_name)
        return sys.modules[lib_name].MemoryProvider(*args, **kwargs)

    raise ValueError(
        f"Loại dịch vụ bộ nhớ không được hỗ trợ: {class_name}. Đường dẫn: {memory_path}"
    )
