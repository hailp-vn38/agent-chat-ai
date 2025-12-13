"""Mô-đun hỗ trợ thiết bị IoT, cung cấp mô tả và xử lý trạng thái"""
from __future__ import annotations
import asyncio
from typing import TYPE_CHECKING
from app.core.logger import setup_logging
from .iot_descriptor import IotDescriptor
if TYPE_CHECKING:
    from app.ai.connection import ConnectionHandler  # chỉ dùng cho hint, không chạy lúc runtime

TAG = __name__
logger = setup_logging()


async def handleIotDescriptors(conn: ConnectionHandler, descriptors):
    """Xử lý mô tả thiết bị IoT"""
    wait_max_time = 5
    while (
        not hasattr(conn, "func_handler")
        or conn.func_handler is None
        or not conn.func_handler.finish_init
    ):
        await asyncio.sleep(1)
        wait_max_time -= 1
        if wait_max_time <= 0:
            logger.bind(tag=TAG).debug("Đối tượng kết nối không có func_handler")
            return

    functions_changed = False

    for descriptor in descriptors:
        # Nếu descriptor không có properties và methods thì bỏ qua
        if "properties" not in descriptor and "methods" not in descriptor:
            continue

        # Xử lý trường hợp thiếu properties
        if "properties" not in descriptor:
            descriptor["properties"] = {}
            # Trích xuất tất cả tham số trong methods thành properties
            if "methods" in descriptor:
                for method_name, method_info in descriptor["methods"].items():
                    if "parameters" in method_info:
                        for param_name, param_info in method_info["parameters"].items():
                            # Chuyển đổi thông tin tham số thành thuộc tính
                            descriptor["properties"][param_name] = {
                                "description": param_info["description"],
                                "type": param_info["type"],
                            }

        # Tạo bộ mô tả thiết bị IoT
        iot_descriptor = IotDescriptor(
            descriptor["name"],
            descriptor["description"],
            descriptor["properties"],
            descriptor["methods"],
        )
        conn.iot_descriptors[descriptor["name"]] = iot_descriptor
        functions_changed = True

    # Nếu có hàm mới, cập nhật danh sách mô tả hàm
    if functions_changed and hasattr(conn, "func_handler"):
        # Đăng ký công cụ IoT với bộ xử lý công cụ hợp nhất
        await conn.func_handler.register_iot_tools(descriptors)

        conn.func_handler.current_support_functions()


async def handleIotStatus(conn: ConnectionHandler, states):
    """Xử lý trạng thái thiết bị IoT"""
    for state in states:
        for key, value in conn.iot_descriptors.items():
            if key == state["name"]:
                for property_item in value.properties:
                    for k, v in state["state"].items():
                        if property_item["name"] == k:
                            if type(v) != type(property_item["value"]):
                                logger.bind(tag=TAG).error(
                                    f"Kiểu giá trị của thuộc tính {property_item['name']} không khớp"
                                )
                                break
                            else:
                                property_item["value"] = v
                                logger.bind(tag=TAG).info(
                                    f"Cập nhật trạng thái IoT: {key}, {property_item['name']} = {v}"
                                )
                            break
                break
