"""Vision Analysis Routes - MCP Vision Integration"""

import base64
import copy
from typing import Optional, Tuple
from fastapi import APIRouter, Depends, Header, Request
from fastapi.responses import JSONResponse, PlainTextResponse, Response
from app.config import Settings
from app.services import ThreadPoolService
from app.api.dependencies import get_settings, get_thread_pool
from app.ai.utils.auth import AuthToken
from app.ai.utils.util import get_vision_url, is_valid_image_file
from app.ai.plugins_func.register import Action
from app.core.logger import setup_logging

TAG = __name__
logger = setup_logging()

router = APIRouter(prefix="/vision", tags=["vision"])

MAX_FILE_SIZE = 5 * 1024 * 1024


def _create_error_response(message: str) -> dict:
    """Tạo cấu trúc phản hồi lỗi thống nhất"""
    return {"success": False, "message": message}


def _verify_auth_token(auth_header: str, auth: AuthToken) -> Tuple[bool, Optional[str]]:
    """Xác thực token"""
    if not auth_header or not auth_header.startswith("Bearer "):
        return False, None

    token = auth_header[7:]
    return auth.verify_token(token)


def _add_cors_headers(response: Response):
    """Thêm header CORS"""
    response.headers["Access-Control-Allow-Headers"] = (
        "client-id, content-type, device-id"
    )
    response.headers["Access-Control-Allow-Credentials"] = "true"
    response.headers["Access-Control-Allow-Origin"] = "*"


@router.options("", include_in_schema=False)
@router.options("/explain", include_in_schema=False)
async def vision_options():
    """Handle CORS preflight requests"""
    response = Response()
    _add_cors_headers(response)
    return response


@router.get("", include_in_schema=True)
@router.get("/explain", include_in_schema=True)
async def vision_get(
    settings: Settings = Depends(get_settings),
):
    """
    Vision GET - Returns vision service status (legacy-compatible)
    """
    response: Response
    try:
        config = settings.to_dict()
        vision_explain = get_vision_url(config)

        if vision_explain and len(vision_explain) > 0 and vision_explain != "null":
            message = f"Giao diện MCP Vision đang chạy bình thường, địa chỉ giao diện giải thích thị giác là: {vision_explain}"
        else:
            message = "Giao diện MCP Vision không chạy bình thường, vui lòng mở file .config.yaml trong thư mục data, tìm【server.vision_explain】, và cấu hình địa chỉ"

        response = PlainTextResponse(content=message)
    except Exception as e:
        logger.bind(tag=TAG).error(f"Lỗi yêu cầu GET MCP Vision: {e}")
        response = JSONResponse(_create_error_response("Lỗi máy chủ nội bộ"))
    _add_cors_headers(response)
    return response


@router.post("", include_in_schema=True)
@router.post("/explain", include_in_schema=True)
async def vision_post(
    request: Request,
    device_id: str = Header(..., alias="Device-Id"),
    client_id: str = Header(..., alias="Client-Id"),
    authorization: str = Header(..., alias="Authorization"),
    settings: Settings = Depends(get_settings),
    thread_pool: ThreadPoolService = Depends(get_thread_pool),
):
    """
    Vision POST - Analyzes image with question (legacy-compatible)
    """
    response: Response
    try:
        config = settings.to_dict()
        secret_key = config.get("server", {}).get("auth_key", "")
        auth = AuthToken(secret_key)

        is_valid, token_device_id = _verify_auth_token(authorization, auth)
        if not is_valid:
            response = JSONResponse(
                _create_error_response("Token xác thực không hợp lệ hoặc đã hết hạn"),
                status_code=401,
            )
            _add_cors_headers(response)
            return response

        if device_id != token_device_id:
            raise ValueError("ID thiết bị không khớp với token")

        form_data = await request.form()

        question = form_data.get("question")
        if not question:
            raise ValueError("Thiếu trường câu hỏi")

        image_file = form_data.get("image")
        if not image_file:
            raise ValueError("Thiếu tệp hình ảnh")

        image_data = await image_file.read()
        if not image_data:
            raise ValueError("Dữ liệu hình ảnh trống")

        if len(image_data) > MAX_FILE_SIZE:
            raise ValueError(
                f"Kích thước hình ảnh vượt quá giới hạn, tối đa cho phép {MAX_FILE_SIZE/1024/1024}MB"
            )

        if not is_valid_image_file(image_data):
            raise ValueError(
                "Định dạng tệp không được hỗ trợ, vui lòng tải lên tệp hình ảnh hợp lệ (hỗ trợ các định dạng JPEG, PNG, GIF, BMP, TIFF, WEBP)"
            )

        image_base64 = base64.b64encode(image_data).decode("utf-8")

        current_config = copy.deepcopy(config)
        # read_config_from_api = current_config.get("read_config_from_api", False)
        # if read_config_from_api:
        #     from app.ai.config_loader import get_private_config_from_api

        #     current_config = get_private_config_from_api(
        #         current_config,
        #         device_id,
        #         client_id,
        #     )

        select_vllm_module = current_config.get("selected_module", {}).get("VLLM")
        if not select_vllm_module:
            raise ValueError("Bạn chưa đặt mô-đun phân tích thị giác mặc định")

        vllm_config = current_config.get("VLLM", {}).get(select_vllm_module, {})
        vllm_type = vllm_config.get("type", select_vllm_module)

        if not vllm_type:
            raise ValueError(
                f"Không thể tìm thấy nhà cung cấp tương ứng với mô-đun VLLM {vllm_type}"
            )

        def _analyze_vision_sync():
            from app.ai.utils.vllm import create_instance

            vllm = create_instance(vllm_type, vllm_config)
            return vllm.response(question, image_base64)

        result = await thread_pool.run_blocking(_analyze_vision_sync)

        return_json = {
            "success": True,
            "action": Action.RESPONSE.name,
            "response": result,
        }
        response = JSONResponse(return_json)

    except ValueError as e:
        return_json = _create_error_response(str(e))
        response = JSONResponse(return_json)
        logger.bind(tag=TAG).error(f"Lỗi yêu cầu POST MCP Vision: {e}")
    except Exception as e:
        return_json = _create_error_response("Đã xảy ra lỗi khi xử lý yêu cầu")
        response = JSONResponse(return_json)
        logger.bind(tag=TAG).error(f"Lỗi yêu cầu POST MCP Vision: {e}")

    _add_cors_headers(response)
    return response
