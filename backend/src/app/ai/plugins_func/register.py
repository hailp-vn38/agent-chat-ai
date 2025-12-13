from app.core.logger import setup_logging
from enum import Enum

TAG = __name__

logger = setup_logging()


class ToolType(Enum):
    NONE = (1, "Sau khi gọi công cụ xong, không thực hiện thao tác nào khác")
    WAIT = (2, "Gọi công cụ và chờ hàm trả về")
    CHANGE_SYS_PROMPT = (3, "Chỉnh sửa prompt hệ thống để chuyển tính cách hoặc nhiệm vụ của vai trò")
    SYSTEM_CTL = (
        4,
        "Điều khiển hệ thống, ảnh hưởng tới luồng hội thoại như thoát, phát nhạc..., cần truyền tham số conn",
    )
    IOT_CTL = (5, "Điều khiển thiết bị IoT, cần truyền tham số conn")
    MCP_CLIENT = (6, "Khách hàng MCP")

    def __init__(self, code, message):
        self.code = code
        self.message = message


class Action(Enum):
    ERROR = (-1, "Lỗi")
    NOTFOUND = (0, "Không tìm thấy hàm")
    NONE = (1, "Không làm gì")
    RESPONSE = (2, "Trả lời trực tiếp")
    REQLLM = (3, "Gọi hàm xong rồi yêu cầu LLM tạo phản hồi")

    def __init__(self, code, message):
        self.code = code
        self.message = message


class ActionResponse:
    def __init__(self, action: Action, result=None, response=None):
        self.action = action  # Loại hành động
        self.result = result  # Kết quả do hành động tạo ra
        self.response = response  # Nội dung trả lời trực tiếp


class FunctionItem:
    def __init__(self, name, description, func, type):
        self.name = name
        self.description = description
        self.func = func
        self.type = type


class DeviceTypeRegistry:
    """Bảng đăng ký loại thiết bị, dùng để quản lý thiết bị IoT và các hàm của chúng"""

    def __init__(self):
        self.type_functions = {}  # type_signature -> {func_name: FunctionItem}

    def generate_device_type_id(self, descriptor):
        """Tạo ID loại thiết bị dựa trên mô tả khả năng"""
        properties = sorted(descriptor["properties"].keys())
        methods = sorted(descriptor["methods"].keys())
        # Dùng tổ hợp thuộc tính và phương thức làm định danh duy nhất
        type_signature = f"{descriptor['name']}:{','.join(properties)}:{','.join(methods)}"
        return type_signature

    def get_device_functions(self, type_id):
        """Lấy tất cả hàm tương ứng với loại thiết bị"""
        return self.type_functions.get(type_id, {})

    def register_device_type(self, type_id, functions):
        """Đăng ký loại thiết bị và các hàm của nó"""
        if type_id not in self.type_functions:
            self.type_functions[type_id] = functions


# Khởi tạo từ điển đăng ký hàm
all_function_registry = {}


def register_function(name, desc, type=None):
    """Decorator đăng ký hàm vào từ điển"""

    def decorator(func):
        all_function_registry[name] = FunctionItem(name, desc, func, type)
        logger.bind(tag=TAG).debug(f"Hàm '{name}' đã được tải, có thể đăng ký sử dụng")
        return func

    return decorator


def register_device_function(name, desc, type=None):
    """Decorator đăng ký hàm cấp thiết bị vào từ điển"""

    def decorator(func):
        logger.bind(tag=TAG).debug(f"Hàm thiết bị '{name}' đã được tải")
        return func

    return decorator


class FunctionRegistry:
    def __init__(self):
        self.function_registry = {}
        self.logger = setup_logging()

    def register_function(self, name, func_item=None):
        # Nếu cung cấp func_item thì đăng ký trực tiếp
        if func_item:
            self.function_registry[name] = func_item
            self.logger.bind(tag=TAG).debug(f"Hàm '{name}' đã đăng ký trực tiếp thành công")
            return func_item

        # Nếu không thì tìm trong all_function_registry
        func = all_function_registry.get(name)
        if not func:
            self.logger.bind(tag=TAG).error(f"Không tìm thấy hàm '{name}'")
            return None
        self.function_registry[name] = func
        self.logger.bind(tag=TAG).debug(f"Hàm '{name}' đã đăng ký thành công")
        return func

    def unregister_function(self, name):
        # Hủy đăng ký hàm, kiểm tra xem có tồn tại không
        if name not in self.function_registry:
            self.logger.bind(tag=TAG).error(f"Không tìm thấy hàm '{name}'")
            return False
        self.function_registry.pop(name, None)
        self.logger.bind(tag=TAG).info(f"Hủy đăng ký hàm '{name}' thành công")
        return True

    def get_function(self, name):
        return self.function_registry.get(name)

    def get_all_functions(self):
        return self.function_registry

    def get_all_function_desc(self):
        return [func.description for _, func in self.function_registry.items()]
