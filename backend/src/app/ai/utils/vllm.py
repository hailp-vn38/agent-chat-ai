import os
import sys
import importlib

# Thêm thư mục gốc dự án vào đường dẫn Python
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, "..", "..", ".."))
sys.path.insert(0, project_root)

from app.core.logger import setup_logging

logger = setup_logging()


def create_instance(class_name, *args, **kwargs):
    # Tạo instance VLLM
    # Đường dẫn trong src/app/ai/providers/vllm
    vllm_path = os.path.join(
        project_root, "app", "ai", "providers", "vllm", f"{class_name}.py"
    )

    if os.path.exists(vllm_path):
        lib_name = f"app.ai.providers.vllm.{class_name}"
        if lib_name not in sys.modules:
            sys.modules[lib_name] = importlib.import_module(lib_name)
        return sys.modules[lib_name].VLLMProvider(*args, **kwargs)

    raise ValueError(
        f"Loại VLLM không được hỗ trợ: {class_name}, vui lòng kiểm tra cấu hình type. Đường dẫn: {vllm_path}"
    )
