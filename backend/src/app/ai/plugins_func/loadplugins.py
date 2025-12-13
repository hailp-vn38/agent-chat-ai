import importlib
import pkgutil
from app.core.logger import setup_logging

TAG = __name__

logger = setup_logging()


def auto_import_modules(package_name):
    """
    Tự động nhập tất cả các mô-đun trong gói được chỉ định.

    Args:
        package_name (str): Tên của gói, ví dụ 'functions'.
    """
    # Lấy đường dẫn của gói
    package = importlib.import_module(package_name)
    package_path = package.__path__

    # Duyệt qua tất cả mô-đun trong gói (bao gồm subpackages)
    for _, module_name, ispkg in pkgutil.iter_modules(package_path):
        # Nhập mô-đun
        full_module_name = f"{package_name}.{module_name}"
        try:
            importlib.import_module(full_module_name)
            # logger.bind(tag=TAG).info(f"mô-đun '{full_module_name}' đã được tải")
        except Exception as e:
            logger.bind(tag=TAG).warning(
                f"Lỗi nhập mô-đun '{full_module_name}': {str(e)}"
            )
