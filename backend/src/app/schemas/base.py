"""
Base Request/Response Schemas - dùng chung cho OTA, Vision, WebSocket
"""

from typing import Any, Dict, Generic, List, Optional, TypeVar

from pydantic import BaseModel, ConfigDict, Field

DataT = TypeVar("DataT")


class WebSocketMessage(BaseModel):
    """Thông điệp WebSocket cơ bản."""

    type: str = Field(..., description="Loại thông điệp: hello, chat, audio, ...")
    data: Optional[str] = None
    content: Optional[str] = None


class ChatRequest(BaseModel):
    """Payload gửi tới endpoint chat."""

    text: str = Field(..., min_length=1, max_length=10000)
    device_id: Optional[str] = None
    session_id: Optional[str] = None


class ChatResponse(BaseModel):
    """Phản hồi từ endpoint chat."""

    text: str
    device_id: Optional[str] = None
    session_id: Optional[str] = None


class OTAInfo(BaseModel):
    """Thông tin OTA cơ bản."""

    status: str
    message: str
    version: Optional[str] = None


class OTAUpdate(BaseModel):
    """Payload yêu cầu cập nhật OTA."""

    version: str
    url: str
    checksum: Optional[str] = None
    force: bool = False


class OTADeviceData(BaseModel):
    """
    Dữ liệu thiết bị gửi lên từ ESP32 trong request body OTA POST.

    Hỗ trợ các field cơ bản + extra fields từ các phiên bản firmware khác nhau.
    Ví dụ: application, device, model, board, v.v.
    """

    application: Optional[Dict[str, Any]] = Field(
        default=None, description="Thông tin ứng dụng: {version, ...}"
    )
    device: Optional[Dict[str, Any]] = Field(
        default=None, description="Thông tin thiết bị: {model, ...}"
    )
    model: Optional[str] = Field(default=None, description="Model thiết bị")

    model_config = ConfigDict(
        extra="allow"
    )  # Accept thêm fields từ firmware versions khác


class VisionRequest(BaseModel):
    """Yêu cầu phân tích thị giác."""

    image: str = Field(..., description="Ảnh base64 hoặc URL ảnh")
    prompt: Optional[str] = None
    model: Optional[str] = None


class VisionResponse(BaseModel):
    """Phản hồi phân tích thị giác."""

    status: str
    result: str
    confidence: Optional[float] = None
    details: Optional[Dict[str, Any]] = None


class HealthResponse(BaseModel):
    """Phản hồi kiểm tra sức khỏe dịch vụ."""

    status: str
    version: str
    message: str


class ErrorResponse(BaseModel):
    """Phản hồi lỗi chung."""

    error: str
    detail: Optional[str] = None
    code: Optional[int] = None


class SuccessResponse(BaseModel, Generic[DataT]):
    """Generic success response wrapper for single item"""

    success: bool = True
    message: str = "Success"
    data: DataT


class PaginatedResponse(BaseModel, Generic[DataT]):
    """Generic paginated response wrapper"""

    success: bool = True
    message: str = "Success"
    data: List[DataT]
    total: int = Field(..., description="Total number of items")
    page: int = Field(..., description="Current page number")
    page_size: int = Field(..., description="Items per page")
    total_pages: int = Field(..., description="Total number of pages")
