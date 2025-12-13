import os
import sys
import importlib
from app.ai.utils.paths import get_ai_dir



from app.core.logger import setup_logging

logger = setup_logging()


def create_instance(class_name, *args, **kwargs):
    # Tạo instance LLM
    llm_path = os.path.join(
        get_ai_dir(), "providers", "llm", class_name, f"{class_name}.py"
    )

    if os.path.exists(llm_path):
        lib_name = f"app.ai.providers.llm.{class_name}.{class_name}"
        if lib_name not in sys.modules:
            sys.modules[lib_name] = importlib.import_module(lib_name)
        return sys.modules[lib_name].LLMProvider(*args, **kwargs)

    raise ValueError(
        f"Loại LLM không được hỗ trợ: {class_name}, vui lòng kiểm tra cấu hình type. Đường dẫn: {llm_path}"
    )
