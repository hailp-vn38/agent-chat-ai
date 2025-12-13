from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Union


from app.ai.plugins_func.register import (
    register_function,
    ToolType,
    ActionResponse,
    Action,
)
from app.core.db.database import local_session
from app.core.logger import setup_logging
from app.crud.crud_reminders import crud_reminders
from app.models.reminder import ReminderStatus

TAG = __name__
logger = setup_logging()


create_reminder_function_desc = {
    "type": "function",
    "function": {
        "name": "create_reminder",
        "description": "Tạo một lời nhắc cho người dùng tại thời điểm chỉ định. Hãy đảm bảo thời gian ở định dạng ISO 8601 và nêu rõ nội dung cần nhắc.",
        "parameters": {
            "type": "object",
            "properties": {
                "reminder_time": {
                    "type": "string",
                    "description": "Thời gian thực hiện lời nhắc ở định dạng ISO-8601, ví dụ: 2024-05-01T18:00:00+07:00",
                },
                "content": {
                    "type": "string",
                    "description": "Nội dung lời nhắc cần phát cho người dùng",
                },
                "title": {
                    "type": "string",
                    "description": "Tiêu đề ngắn gọn của lời nhắc (tùy chọn)",
                },
                "metadata": {
                    "type": "object",
                    "description": "Dữ liệu phụ trợ cần lưu cho lời nhắc (tùy chọn)",
                },
            },
            "required": ["reminder_time", "content"],
        },
    },
}

list_reminder_function_desc = {
    "type": "function",
    "function": {
        "name": "get_list_reminder",
        "description": "Lấy danh sách lời nhắc cho thiết bị hiện tại, có thể lọc theo khoảng thời gian (today/week) và trạng thái (pending/completed).",
        "parameters": {
            "type": "object",
            "properties": {
                "period": {
                    "type": "string",
                    "enum": ["today", "week"],
                    "description": "Khoảng thời gian lọc lời nhắc: 'today' (mặc định) hoặc 'week'.",
                },
                "status": {
                    "type": "string",
                    "enum": ["pending", "completed"],
                    "description": "Trạng thái lời nhắc: 'pending' (chưa hoàn thành) hoặc 'completed' (đã gửi/đã xác nhận).",
                },
            },
        },
    },
}

delete_reminder_function_desc = {
    "type": "function",
    "function": {
        "name": "delete_reminder",
        "description": "Xóa một hoặc nhiều lời nhắc dựa trên danh sách UUID bản ghi reminder.",
        "parameters": {
            "type": "object",
            "properties": {
                "ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "minItems": 1,
                    "description": "Danh sách UUID của bản ghi reminder trong cơ sở dữ liệu.",
                }
            },
            "required": ["ids"],
        },
    },
}

update_status_reminder_function_desc = {
    "type": "function",
    "function": {
        "name": "update_status_reminder",
        "description": "Cập nhật trạng thái của một lời nhắc dựa trên UUID bản ghi reminder.",
        "parameters": {
            "type": "object",
            "properties": {
                "id": {
                    "type": "string",
                    "description": "UUID của bản ghi reminder cần cập nhật trạng thái.",
                },
                "status": {
                    "type": "string",
                    "enum": ["pending", "delivered", "received", "failed"],
                    "description": "Trạng thái mới cho lời nhắc: 'pending', 'delivered', 'received', hoặc 'failed'.",
                },
            },
            "required": ["id", "status"],
        },
    },
}


def _resolve_reminder_context(
    conn,
) -> tuple[
    Optional[Any], Optional[str], Optional[str], Optional[str], Optional[ActionResponse]
]:
    """
    Resolve reminder context từ connection.
    Yêu cầu: agent_id (UUID), device_id (UUID), và device_mac_address (MAC string)

    Returns: (reminder_service, agent_id, device_id, mac_address, error_response)
    """
    reminder_service = getattr(getattr(conn, "server", None), "reminder_service", None)
    if reminder_service is None:
        logger.bind(tag=TAG).warning("Reminder service chưa được khởi tạo")
        return (
            None,
            None,
            None,
            None,
            ActionResponse(
                action=Action.RESPONSE,
                result="Reminder service unavailable",
                response="Máy chủ chưa sẵn sàng để xử lý lời nhắc, vui lòng thử lại sau.",
            ),
        )

    agent_id = getattr(conn, "agent_id", None)
    if not agent_id:
        logger.bind(tag=TAG).warning("Không xác định được agent_id cho lời nhắc")
        return (
            None,
            None,
            None,
            None,
            ActionResponse(
                action=Action.RESPONSE,
                result="Missing agent_id",
                response="Không thể thực hiện vì agent chưa được xác định.",
            ),
        )

    device_id = getattr(conn, "device_id", None)
    if not device_id:
        logger.bind(tag=TAG).warning("Không xác định được device_id cho lời nhắc")
        return (
            None,
            None,
            None,
            None,
            ActionResponse(
                action=Action.RESPONSE,
                result="Missing device_id",
                response="Không thể thực hiện vì thiết bị chưa được xác định.",
            ),
        )

    # MAC address cho MQTT
    mac_address = getattr(conn, "device_mac_address", None)
    if not mac_address:
        logger.bind(tag=TAG).warning("Không xác định được MAC address cho lời nhắc")
        return (
            None,
            None,
            None,
            None,
            ActionResponse(
                action=Action.RESPONSE,
                result="Missing mac_address",
                response="Không thể thực hiện vì MAC address chưa được xác định.",
            ),
        )

    mac_address = mac_address.strip().upper()
    return reminder_service, str(agent_id), str(device_id), mac_address, None


def _parse_reminder_time(
    reminder_time: Union[str, float, int],
    tz,
) -> datetime:
    """Chuyển chuỗi thời gian hoặc timestamp sang datetime có timezone"""
    if isinstance(reminder_time, (int, float)):
        dt = datetime.fromtimestamp(reminder_time, tz=timezone.utc)
    elif isinstance(reminder_time, str):
        try:
            dt = datetime.fromisoformat(reminder_time)
        except ValueError as exc:
            raise ValueError(
                "Thời gian lời nhắc phải ở định dạng ISO 8601, ví dụ 2024-05-01T18:00:00+07:00"
            ) from exc
    else:
        raise ValueError("Không hỗ trợ định dạng thời gian được cung cấp")

    if dt.tzinfo is None:
        return dt.replace(tzinfo=tz)
    return dt.astimezone(tz)


@register_function(
    "create_reminder", create_reminder_function_desc, ToolType.SYSTEM_CTL
)
async def create_reminder(
    conn,
    reminder_time: Union[str, float, int],
    content: str,
    title: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
):
    logger.bind(tag=TAG).debug("Tạo lời nhắc mới được yêu cầu")
    reminder_service, agent_id_str, device_id_str, mac_address, error_response = (
        _resolve_reminder_context(conn)
    )
    if error_response:
        return error_response
    logger.bind(tag=TAG).debug(
        f"Agent: agent_id={agent_id_str}, device_id={device_id_str}, mac={mac_address}"
    )

    try:
        tz = reminder_service.scheduler_service.timezone
        remind_at = _parse_reminder_time(reminder_time, tz)
        logger.bind(tag=TAG).debug(
            f"Thời gian nhắc nhở sau chuẩn hóa: {remind_at.isoformat()}"
        )
    except ValueError as exc:
        logger.bind(tag=TAG).warning(f"Không thể phân tích reminder_time: {exc}")
        return ActionResponse(
            action=Action.REQLLM,
            result=json.dumps(
                {"message": "tao_that_bai", "reason": str(exc)}, ensure_ascii=False
            ),
            response=None,
        )

    try:
        if metadata and not isinstance(metadata, dict):
            if isinstance(metadata, str):
                try:
                    metadata = json.loads(metadata)
                except json.JSONDecodeError:
                    metadata = {"raw": metadata}
            else:
                metadata = {"raw": str(metadata)}

        reminder_record = await reminder_service.create_and_schedule_reminder(
            remind_at=remind_at,
            content=content,
            agent_id=agent_id_str,
            device_id=device_id_str,
            mac_address=mac_address,
            title=title,
            metadata=metadata,
        )
        logger.bind(tag=TAG).debug(
            f"Nhắc nhở đã lưu vào DB với reminder_id={reminder_record.reminder_id}"
        )
    except ValueError as exc:
        logger.bind(tag=TAG).warning(f"Lên lịch lời nhắc thất bại: {exc}")
        return ActionResponse(
            action=Action.REQLLM,
            result=json.dumps(
                {"message": "tao_that_bai", "reason": str(exc)}, ensure_ascii=False
            ),
            response=None,
        )
    except Exception as exc:  # pragma: no cover - unexpected failure
        logger.bind(tag=TAG).exception(f"Lỗi bất ngờ khi tạo lời nhắc: {exc}")
        return ActionResponse(
            action=Action.REQLLM,
            result=json.dumps(
                {
                    "message": "tao_that_bai",
                    "reason": "loi_noi_bo",
                    "detail": "Không thể tạo lời nhắc, vui lòng thử lại.",
                },
                ensure_ascii=False,
            ),
            response=None,
        )

    tz_display = reminder_service.scheduler_service.timezone
    remind_at_local_str = (
        reminder_record.remind_at_local.astimezone(tz_display).isoformat()
        if reminder_record.remind_at_local.tzinfo
        else reminder_record.remind_at_local.replace(tzinfo=tz_display).isoformat()
    )
    remind_at_utc_str = reminder_record.remind_at.astimezone(timezone.utc).isoformat()

    result_payload = {
        "message": "da_tao_thanh_cong",
        "id": str(reminder_record.id),
        # "reminder_id": reminder_record.reminder_id,
        "title": reminder_record.title or "",
        "content": reminder_record.content,
        "remind_at": remind_at_utc_str,
        "remind_at_local": remind_at_local_str,
        "status": getattr(reminder_record.status, "value", str(reminder_record.status)),
        # "metadata": metadata or {},
    }
    logger.bind(tag=TAG).debug(
        f"Tạo lời nhắc thành công {reminder_record.reminder_id} cho thiết bị {mac_address}"
    )
    return ActionResponse(
        action=Action.REQLLM,
        result=json.dumps(result_payload, ensure_ascii=False),
        response=None,
    )


@register_function(
    "get_list_reminder", list_reminder_function_desc, ToolType.SYSTEM_CTL
)
async def get_list_reminder(conn, period: str = "today", status: Optional[str] = None):
    logger.bind(tag=TAG).info(
        f"Yêu cầu lấy danh sách lời nhắc period={period}, status={status}"
    )
    reminder_service, agent_id_str, device_id_str, mac_address, error_response = (
        _resolve_reminder_context(conn)
    )
    if error_response:
        return error_response

    try:
        period_value = (period or "today").lower()
        status_value = status.lower() if status else None
        reminders = await reminder_service.list_reminders(
            agent_id=agent_id_str,
            device_id=device_id_str,
            period=period_value,
            status_filter=status_value,
            mac_address=mac_address,
        )
    except ValueError as exc:
        logger.bind(tag=TAG).warning(
            f"Lấy danh sách lời nhắc thất bại vì dữ liệu không hợp lệ: {exc}"
        )
        return ActionResponse(
            action=Action.REQLLM,
            result=json.dumps(
                {"message": "danh_sach_loi", "reason": str(exc)}, ensure_ascii=False
            ),
            response=None,
        )
    except Exception as exc:  # pragma: no cover - unexpected failure
        logger.bind(tag=TAG).exception(f"Lỗi bất ngờ khi lấy danh sách lời nhắc: {exc}")
        return ActionResponse(
            action=Action.REQLLM,
            result=json.dumps(
                {
                    "message": "danh_sach_loi",
                    "reason": "internal_error",
                    "detail": "Không thể lấy danh sách lời nhắc, vui lòng thử lại.",
                },
                ensure_ascii=False,
            ),
            response=None,
        )

    tz_display = reminder_service.scheduler_service.timezone
    reminders_payload = []
    for item in reminders:
        remind_at_local = (
            item.remind_at_local.astimezone(tz_display)
            if item.remind_at_local.tzinfo
            else item.remind_at_local.replace(tzinfo=tz_display)
        )
        reminders_payload.append(
            {
                "id": str(item.id),
                # "reminder_id": item.reminder_id,
                "title": item.title or "",
                "content": item.content,
                "remind_at": item.remind_at.astimezone(timezone.utc).isoformat(),
                "remind_at_local": remind_at_local.isoformat(),
                "status": getattr(item.status, "value", str(item.status)),
            }
        )

    response_payload = {
        "reminders": reminders_payload,
        "message": "danh_sach_thanh_cong" if reminders_payload else "khong_co_nhac_nho",
    }
    return ActionResponse(
        action=Action.REQLLM,
        result=json.dumps(response_payload, ensure_ascii=False),
        response=None,
    )


@register_function(
    "delete_reminder", delete_reminder_function_desc, ToolType.SYSTEM_CTL
)
async def delete_reminder(conn, ids: list[str]):
    logger.bind(tag=TAG).info(f"Yêu cầu xóa lời nhắc {ids}")
    reminder_service, agent_id_str, device_id_str, mac_address, error_response = (
        _resolve_reminder_context(conn)
    )
    if error_response:
        return error_response

    if not ids or not isinstance(ids, list):
        logger.bind(tag=TAG).warning("Danh sách ids không hợp lệ để xóa")
        return ActionResponse(
            action=Action.REQLLM,
            result=json.dumps(
                {"message": "xoa_that_bai", "reason": "ids_khong_hop_le"},
                ensure_ascii=False,
            ),
            response=None,
        )

    id_list = [item.strip() for item in ids if isinstance(item, str) and item.strip()]
    if not id_list:
        logger.bind(tag=TAG).warning("Không có id hợp lệ trong danh sách yêu cầu xóa")
        return ActionResponse(
            action=Action.REQLLM,
            result=json.dumps(
                {"message": "xoa_that_bai", "reason": "ids_khong_hop_le"},
                ensure_ascii=False,
            ),
            response=None,
        )

    try:
        deleted = await reminder_service.delete_reminders_by_ids(
            reminder_db_ids=id_list,
            agent_id=agent_id_str,
            device_id=device_id_str,
            mac_address=mac_address,
        )
    except ValueError as exc:
        logger.bind(tag=TAG).warning(
            f"Không thể xóa reminder vì dữ liệu không hợp lệ: {exc}"
        )
        return ActionResponse(
            action=Action.REQLLM,
            result=json.dumps(
                {"message": "xoa_that_bai", "reason": str(exc)}, ensure_ascii=False
            ),
            response=None,
        )
    except Exception as exc:  # pragma: no cover - unexpected failure
        logger.bind(tag=TAG).exception(
            f"Lỗi bất ngờ khi xóa reminders {id_list}: {exc}"
        )
        return ActionResponse(
            action=Action.REQLLM,
            result=json.dumps(
                {"message": "xoa_that_bai", "reason": "loi_noi_bo"},
                ensure_ascii=False,
            ),
            response=None,
        )

    if not deleted:
        return ActionResponse(
            action=Action.REQLLM,
            result=json.dumps(
                {"message": "xoa_that_bai", "reason": "khong_tim_thay"},
                ensure_ascii=False,
            ),
            response=None,
        )

    return ActionResponse(
        action=Action.REQLLM,
        result=json.dumps(
            {"message": "da_xoa_thanh_cong", "ids": id_list}, ensure_ascii=False
        ),
        response=None,
    )


@register_function(
    "update_status_reminder", update_status_reminder_function_desc, ToolType.SYSTEM_CTL
)
async def update_status_reminder(conn, id: str, status: str):
    """
    Cập nhật trạng thái của một lời nhắc.

    Args:
        conn: Connection object chứa reminder_service, agent_id, device_id, device_mac_address
        id: UUID của reminder cần cập nhật
        status: Trạng thái mới (pending/delivered/received/failed)

    Returns:
        ActionResponse với kết quả cập nhật
    """
    logger.bind(tag=TAG).info(
        f"Yêu cầu cập nhật trạng thái reminder {id} thành {status}"
    )
    reminder_service, agent_id_str, device_id_str, mac_address, error_response = (
        _resolve_reminder_context(conn)
    )
    if error_response:
        return error_response

    # Validate status
    status_mapping = {
        "pending": ReminderStatus.PENDING,
        "delivered": ReminderStatus.DELIVERED,
        "received": ReminderStatus.RECEIVED,
        "failed": ReminderStatus.FAILED,
    }
    status_lower = status.lower().strip()
    if status_lower not in status_mapping:
        logger.bind(tag=TAG).warning(f"Trạng thái không hợp lệ: {status}")
        return ActionResponse(
            action=Action.REQLLM,
            result=json.dumps(
                {
                    "message": "cap_nhat_that_bai",
                    "reason": "trang_thai_khong_hop_le",
                    "detail": f"Trạng thái phải là một trong: {', '.join(status_mapping.keys())}",
                },
                ensure_ascii=False,
            ),
            response=None,
        )

    try:
        async with local_session() as db:
            updated_reminder = await crud_reminders.update_status_by_id(
                db=db,
                reminder_id=id,
                new_status=status_mapping[status_lower],
            )

        logger.bind(tag=TAG).info(
            f"Đã cập nhật trạng thái reminder {id} thành {status}"
        )

        tz_display = reminder_service.scheduler_service.timezone
        remind_at_local = (
            updated_reminder.remind_at_local.astimezone(tz_display)
            if updated_reminder.remind_at_local.tzinfo
            else updated_reminder.remind_at_local.replace(tzinfo=tz_display)
        )

        result_payload = {
            "message": "da_cap_nhat_thanh_cong",
            "id": str(updated_reminder.id),
            "title": updated_reminder.title or "",
            "content": updated_reminder.content,
            "remind_at": updated_reminder.remind_at.astimezone(
                timezone.utc
            ).isoformat(),
            "remind_at_local": remind_at_local.isoformat(),
            "status": getattr(
                updated_reminder.status, "value", str(updated_reminder.status)
            ),
        }

        return ActionResponse(
            action=Action.REQLLM,
            result=json.dumps(result_payload, ensure_ascii=False),
            response=None,
        )

    except Exception as exc:
        logger.bind(tag=TAG).exception(f"Lỗi khi cập nhật trạng thái: {exc}")
        return ActionResponse(
            action=Action.REQLLM,
            result=json.dumps(
                {"message": "cap_nhat_that_bai", "reason": "loi_noi_bo"},
                ensure_ascii=False,
            ),
            response=None,
        )
