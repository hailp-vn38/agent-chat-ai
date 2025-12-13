"""
Reminder Service - Quản lý scheduler và MQTT để phát nhắc nhở
"""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import FastAPI
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.jobstores.base import JobLookupError
from apscheduler.events import EVENT_JOB_MISSED
from sqlalchemy.exc import NoResultFound

from app.config.settings import (
    ReminderSettings,
    ReminderSchedulerSettings,
    ReminderJobStoreSettings,
    ServerSettings,
)
from app.services.mqtt_service import MQTTService
from app.core.db.database import local_session
from app.crud.crud_reminders import crud_reminders
from app.models.reminder import ReminderStatus
from app.schemas.reminder import (
    ReminderCreateInternal,
    ReminderRead,
    ReminderListRead,
    ReminderUpdateInternal,
)
from app.core.logger import setup_logging
from app.core.utils.timezone import resolve_timezone
from app.ai.utils.device_connection_utils import is_device_online
from app.ai.handle.textHandler.notificationMessageHandler import (
    NotificationMessageHandler,
)

TAG = __name__

_REMINDER_SERVICE_REGISTRY: Dict[str, "ReminderService"] = {}


async def _execute_scheduled_reminder(
    payload: Dict[str, Any], service_key: str
) -> None:
    logger = setup_logging()
    service = _REMINDER_SERVICE_REGISTRY.get(service_key)
    if not service:
        logger.bind(tag=TAG).warning(
            f"Không tìm thấy ReminderService với khóa {service_key} để xử lý lời nhắc"
        )
        return
    await service._on_reminder_due(payload)


class ReminderSchedulerService:
    """Quản lý APScheduler cho nhắc nhở"""

    def __init__(
        self,
        config: ReminderSchedulerSettings,
        timezone_value: Any,
        service_key: str,
    ):
        self.config = config
        self.logger = setup_logging()
        self.service_key = service_key

        job_store = self._prepare_job_store(config.job_store)
        self._timezone = resolve_timezone(timezone_value)
        self._scheduler = AsyncIOScheduler(
            jobstores={"default": job_store}, timezone=self._timezone
        )
        # Đăng ký listener cho missed job event
        self._scheduler.add_listener(self._on_job_missed, EVENT_JOB_MISSED)

    @property
    def timezone(self) -> timezone:
        return self._timezone

    def _prepare_job_store(self, job_store: ReminderJobStoreSettings):
        base_root = Path(__file__).resolve().parents[3]
        folder_input = Path(job_store.folder).expanduser()
        if folder_input.is_absolute():
            folder = folder_input
        else:
            candidate = base_root / folder_input
            if candidate.exists():
                folder = candidate
            else:
                candidate_with_src = base_root / "src" / folder_input
                if candidate_with_src.exists():
                    folder = candidate_with_src
                else:
                    folder = candidate
        folder.mkdir(parents=True, exist_ok=True)
        db_path = folder / job_store.filename
        return SQLAlchemyJobStore(url=f"sqlite:///{db_path}")

    def start(self) -> None:
        if not self._scheduler.running:
            self._scheduler.start()
            self.logger.bind(tag=TAG).info(
                f"Reminder scheduler đã khởi động (missed_job_threshold={self.config.missed_job_threshold}s)"
            )

    async def shutdown(self) -> None:
        if self._scheduler.running:
            # Sử dụng wait=True để cleanup semaphores đúng cách
            self._scheduler.shutdown(wait=True)
            self.logger.bind(tag=TAG).info("Reminder scheduler đã dừng")

    def schedule(
        self,
        reminder_id: str,
        run_at: datetime,
        payload: Dict[str, Any],
    ) -> None:
        if run_at.tzinfo is None:
            run_at = run_at.replace(tzinfo=self._timezone)
        else:
            run_at = run_at.astimezone(self._timezone)

        now = datetime.now(self._timezone)
        if run_at <= now:
            raise ValueError("Lên lịch thất bại: thời gian nhắc nhở phải ở tương lai")

        self._scheduler.add_job(
            _execute_scheduled_reminder,
            trigger="date",
            id=reminder_id,
            run_date=run_at,
            replace_existing=True,
            kwargs={"payload": payload, "service_key": self.service_key},
        )
        self.logger.bind(tag=TAG).info(
            f"Đã lên lịch nhắc nhở {reminder_id} lúc {run_at.isoformat()}"
        )

    def cancel(self, reminder_id: str) -> bool:
        try:
            self._scheduler.remove_job(reminder_id)
            self.logger.bind(tag=TAG).info(
                f"Đã hủy lịch nhắc nhở {reminder_id} khỏi scheduler"
            )
            return True
        except JobLookupError:
            self.logger.bind(tag=TAG).debug(f"Không tìm thấy job {reminder_id} để hủy")
            return False
        except Exception as exc:  # pragma: no cover - defensive logging
            self.logger.bind(tag=TAG).warning(f"Lỗi khi hủy job {reminder_id}: {exc}")
            return False

    def _on_job_missed(self, event) -> None:
        """Event listener khi job bị miss (thời gian chạy đã qua)

        Args:
            event: APScheduler event object chứa thông tin job
                - event.job_id: reminder_id
                - event.exception: Exception nếu có
        """
        reminder_id = event.job_id
        self.logger.bind(tag=TAG).warning(
            f"[Reminder] Job {reminder_id} bị miss, cập nhật status thành FAILED"
        )

        # Cập nhật reminder status thành FAILED không đồng bộ
        try:
            # Lấy service từ registry để gọi _update_reminder
            service = _REMINDER_SERVICE_REGISTRY.get(self.service_key)
            if service:
                # Sử dụng asyncio.create_task để chạy async function từ event handler
                # vì event handler này không async
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    asyncio.create_task(
                        service._update_reminder(
                            reminder_id,
                            status=ReminderStatus.FAILED,
                        )
                    )
                else:
                    self.logger.bind(tag=TAG).warning(
                        f"[Reminder] Event loop không chạy, không thể cập nhật reminder {reminder_id}"
                    )
        except Exception as exc:
            self.logger.bind(tag=TAG).exception(
                f"[Reminder] Lỗi khi xử lý missed job {reminder_id}: {exc}"
            )


@dataclass
class ReminderCreationResult:
    reminder_id: str
    remind_at: datetime
    payload: Dict[str, Any]
    reminder_db_id: str


class ReminderService:
    """Facade dịch vụ nhắc nhở.

    Service này quản lý việc tạo, lên lịch và gửi reminder.
    MQTT service được inject từ bên ngoài để cho phép tái sử dụng và testability.

    Args:
        reminder_config: ReminderSettings config object
        server_config: ServerSettings config object
        mqtt_service: MQTTService instance (optional, inject từ app.state)
    """

    def __init__(
        self,
        reminder_config: ReminderSettings,
        server_config: ServerSettings,
        mqtt_service: Optional[MQTTService] = None,
    ):
        self.logger = setup_logging()
        self.config = reminder_config
        self.server_config = server_config
        self.mqtt_service = mqtt_service
        self.topic_base = (
            getattr(reminder_config.mqtt, "topic_base", "reminder")
            if reminder_config.mqtt
            else "reminder"
        )

        if mqtt_service and mqtt_service.is_available():
            self.logger.bind(tag=TAG).debug(
                f"[Reminder] Sử dụng MQTTService đã inject, topic_base={self.topic_base}"
            )
        else:
            self.logger.bind(tag=TAG).debug(
                "[Reminder] MQTT service không khả dụng hoặc không được inject"
            )

        self.app_state: Optional[FastAPI] = None  # Will be set in init_app()
        self.notification_handler = NotificationMessageHandler()
        configured_key = (reminder_config.service_key or "").strip()
        if not configured_key:
            configured_key = "reminder-service-default"
        self.registry_key = configured_key
        existing_service = _REMINDER_SERVICE_REGISTRY.get(self.registry_key)
        if existing_service and existing_service is not self:
            self.logger.bind(tag=TAG).warning(
                f"Đã tồn tại ReminderService với khóa {self.registry_key}, ghi đè bằng phiên bản mới"
            )
        self.scheduler_service = ReminderSchedulerService(
            reminder_config.scheduler,
            getattr(server_config, "tz", "UTC"),
            self.registry_key,
        )
        _REMINDER_SERVICE_REGISTRY[self.registry_key] = self
        self.logger.bind(tag=TAG).info(
            f"Đăng ký ReminderService với khóa {self.registry_key}"
        )

    def init_app(self, app: FastAPI) -> None:
        self.app_state = app.state
        self.scheduler_service.start()

    async def shutdown(self) -> None:
        await self.scheduler_service.shutdown()
        # Note: MQTTService được shutdown riêng trong main.py
        _REMINDER_SERVICE_REGISTRY.pop(self.registry_key, None)
        self.logger.bind(tag=TAG).info(
            f"Hủy đăng ký ReminderService với khóa {self.registry_key}"
        )

    async def create_reminder_entry(
        self,
        remind_at: datetime,
        content: str,
        agent_id: str,
        device_id: str,
        mac_address: str,
        title: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ReminderRead:
        """
        Tạo bản ghi reminder trong database.

        Args:
            remind_at: Thời gian nhắc nhở
            content: Nội dung lời nhắc
            title: Tiêu đề (optional)
            metadata: Metadata bổ sung (optional)
            agent_id: Agent UUID (bắt buộc)
            device_id: Device UUID (bắt buộc, dùng cho check online)
            mac_address: MAC address (dùng cho logging/MQTT)
        """
        self.logger.bind(tag=TAG).debug(
            f"[Reminder] Bắt đầu tạo bản ghi cho thiết bị {device_id}"
        )
        try:
            if not device_id:
                raise ValueError("device_id là bắt buộc")

            tz = self.scheduler_service.timezone
            if remind_at.tzinfo is None:
                remind_at_local = remind_at.replace(tzinfo=tz)
            else:
                remind_at_local = remind_at.astimezone(tz)

            remind_at_utc = remind_at_local.astimezone(timezone.utc)
            reminder_id = uuid.uuid4().hex

            async with local_session() as db:
                self.logger.bind(tag=TAG).debug(
                    f"[Reminder] Agent UUID={agent_id}, Device UUID={device_id}, chuẩn bị ghi DB"
                )
                reminder_create = ReminderCreateInternal(
                    agent_id=agent_id,
                    content=content,
                    title=title,
                    remind_at=remind_at_utc,
                    reminder_metadata=metadata,
                    reminder_id=reminder_id,
                    remind_at_local=remind_at_local,
                )

                step_start = datetime.now(timezone.utc)
                reminder_record = await crud_reminders.create_reminder_safe(
                    db=db,
                    reminder_create_internal=reminder_create,
                )
                if reminder_record is None:
                    raise RuntimeError("Không thể tạo bản ghi reminder mới")
                self.logger.bind(tag=TAG).debug(
                    f"[Reminder] Ghi reminder vào DB mất {(datetime.now(timezone.utc)-step_start).total_seconds():.2f}s"
                )

            self.logger.bind(tag=TAG).debug(
                f"[Reminder] Đã tạo reminder {reminder_record.reminder_id} trong DB"
            )
            return reminder_record
        except Exception as exc:
            self.logger.bind(tag=TAG).exception(
                f"[Reminder] create_reminder_entry thất bại: {exc}"
            )
            raise

    async def create_and_schedule_reminder(
        self,
        remind_at: datetime,
        content: str,
        agent_id: str,
        device_id: str,
        mac_address: str,
        title: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ReminderRead:
        """
        Tạo bản ghi reminder và lên lịch trong scheduler.

        Args:
            remind_at: Thời gian nhắc nhở
            content: Nội dung lời nhắc
            title: Tiêu đề (optional)
            metadata: Metadata bổ sung (optional)
            agent_id: Agent UUID (bắt buộc)
            device_id: Device UUID (bắt buộc, dùng cho check online)
            mac_address: MAC address (dùng cho MQTT)
        """
        if not agent_id:
            raise ValueError("agent_id là bắt buộc")
        if not device_id:
            raise ValueError("device_id là bắt buộc")

        self.logger.bind(tag=TAG).debug(
            f"[Reminder] create_and_schedule_reminder bắt đầu cho agent={agent_id}, device={device_id}"
        )
        reminder_record = await self.create_reminder_entry(
            remind_at=remind_at,
            content=content,
            title=title,
            metadata=metadata,
            agent_id=agent_id,
            device_id=device_id,
            mac_address=mac_address,
        )
        try:
            self.logger.bind(tag=TAG).debug(
                f"[Reminder] Lên lịch reminder {reminder_record.reminder_id}"
            )
            result = self.schedule_reminder(
                reminder=reminder_record,
                device_id=device_id,
                mac_address=mac_address,
            )
        except Exception as exc:
            await self._update_reminder(
                reminder_record.reminder_id,
                status=ReminderStatus.FAILED,
            )
            self.logger.bind(tag=TAG).error(
                f"[Reminder] Lên lịch reminder {reminder_record.reminder_id} thất bại: {exc}"
            )
            raise exc
        self.logger.bind(tag=TAG).debug(
            f"[Reminder] Hoàn tất create_and_schedule_reminder cho {reminder_record.reminder_id}"
        )
        return reminder_record

    async def list_reminders(
        self,
        agent_id: str,
        device_id: str,
        period: str = "today",
        status_filter: Optional[str] = None,
        mac_address: str = None,
    ) -> list[ReminderListRead]:
        """
        Liệt kê reminders cho agent.

        Args:
            agent_id: Agent UUID (bắt buộc)
            device_id: Device UUID (bắt buộc, dùng cho logging)
            period: "today" hoặc "week"
            status_filter: "pending" hoặc "completed" (optional)
            mac_address: MAC address (dùng cho logging)
        """
        if not agent_id:
            raise ValueError("agent_id là bắt buộc")

        self.logger.bind(tag=TAG).debug(
            f"[Reminder] list_reminders period={period}, status={status_filter} cho agent={agent_id}, device={device_id}"
        )
        try:
            async with local_session() as db:
                if period not in {"today", "week"}:
                    raise ValueError("period phải là 'today' hoặc 'week'")
                is_today = period == "today"

                reminders_result = await crud_reminders.get_reminders_by_agent_filtered(
                    db=db,
                    agent_id=agent_id,
                    is_today=is_today,
                )
            reminders: list[ReminderListRead] = (
                reminders_result.get("data", []) if reminders_result else []
            )
            if status_filter:
                status_filter_lower = status_filter.lower()
                if status_filter_lower not in {"pending", "completed"}:
                    raise ValueError("status chỉ chấp nhận 'pending' hoặc 'completed'")
                if status_filter_lower == "pending":
                    reminders = [
                        reminder
                        for reminder in reminders
                        if reminder.status == ReminderStatus.PENDING
                    ]
                else:
                    reminders = [
                        reminder
                        for reminder in reminders
                        if reminder.status
                        in {
                            ReminderStatus.DELIVERED,
                            ReminderStatus.RECEIVED,
                        }
                    ]
            reminders.sort(key=lambda item: item.remind_at_local)
            self.logger.bind(tag=TAG).debug(
                f"[Reminder] Tìm thấy {len(reminders)} reminder cho {device_id} với period={period} status={status_filter}"
            )
            return reminders
        except Exception as exc:
            self.logger.bind(tag=TAG).exception(
                f"[Reminder] list_reminders thất bại cho {device_id}: {exc}"
            )
            raise

    async def delete_reminders_by_ids(
        self,
        reminder_db_ids: list[str],
        agent_id: str,
        device_id: str,
        mac_address: str = None,
    ) -> bool:
        """
        Xóa reminders theo IDs.

        Args:
            reminder_db_ids: Danh sách ID reminder cần xóa
            agent_id: Agent UUID (bắt buộc)
            device_id: Device UUID (bắt buộc, dùng cho logging)
            mac_address: MAC address (dùng cho logging)
        """
        if not agent_id:
            raise ValueError("agent_id là bắt buộc")

        self.logger.bind(tag=TAG).debug(
            f"[Reminder] delete_reminders_by_ids: ids={reminder_db_ids}, agent={agent_id}, device={device_id}"
        )
        try:
            # Convert string IDs to UUID for database queries
            from uuid import UUID

            reminder_uuids = [UUID(reminder_id) for reminder_id in reminder_db_ids]
            async with local_session() as db:
                reminders_result = await crud_reminders.get_multi(
                    db=db,
                    offset=0,
                    limit=None,
                    schema_to_select=ReminderRead,
                    return_as_model=True,
                    return_total_count=False,
                    id__in=reminder_uuids,
                    agent_id=agent_id,
                    is_deleted=False,
                )
                reminders: list[ReminderRead] = (
                    reminders_result.get("data", [])
                    if isinstance(reminders_result, dict)
                    else reminders_result
                )
                found_ids = {reminder.id for reminder in reminders}
                missing = [
                    reminder_uuid
                    for reminder_uuid in reminder_uuids
                    if reminder_uuid not in found_ids
                ]
                if missing:
                    self.logger.bind(tag=TAG).warning(
                        "Một số reminder không thuộc thiết bị hoặc không tồn tại: "
                        + ", ".join(str(x) for x in missing)
                    )
                    return False

                await crud_reminders.batch_hard_delete_reminders(
                    db=db, reminder_ids=reminder_uuids
                )

            for reminder in reminders:
                reminder_scheduler_id = reminder.reminder_id
                removed = self.scheduler_service.cancel(reminder_scheduler_id)
                if not removed:
                    self.logger.bind(tag=TAG).debug(
                        f"[Reminder] Không có job scheduler nào cho {reminder_scheduler_id} cần hủy"
                    )
            self.logger.bind(tag=TAG).info(
                f"[Reminder] Đã xóa reminder {reminder_db_ids} cho thiết bị {device_id}"
            )
            return True
        except NoResultFound:
            self.logger.bind(tag=TAG).warning(
                f"[Reminder] Không tìm thấy reminders {reminder_db_ids} để xóa cho {device_id}"
            )
            return False
        except ValueError as exc:
            self.logger.bind(tag=TAG).warning(
                f"[Reminder] delete_reminders_by_ids nhận tham số không hợp lệ ({reminder_db_ids}): {exc}"
            )
            raise
        except Exception as exc:
            self.logger.bind(tag=TAG).exception(
                f"[Reminder] delete_reminders_by_ids thất bại cho {device_id}: {exc}"
            )
            raise

    async def _update_reminder(
        self,
        reminder_id: str,
        *,
        status: ReminderStatus | None = None,
        received_at: Optional[datetime] = None,
        increment_retry: bool = False,
    ) -> None:
        self.logger.bind(tag=TAG).debug(
            f"[Reminder] Cập nhật reminder {reminder_id} với dữ liệu: status={status},"
            f" received_at={received_at}, retry={increment_retry}"
        )
        updated = False
        try:
            async with local_session() as db:
                reminder = await crud_reminders.get(
                    db=db,
                    reminder_id=reminder_id,
                    is_deleted=False,
                    schema_to_select=ReminderRead,
                    return_as_model=True,
                )
                if reminder is None:
                    self.logger.bind(tag=TAG).warning(
                        f"[Reminder] Không tìm thấy reminder {reminder_id} để cập nhật"
                    )
                    return

                update_payload: Dict[str, Any] = {}
                if status is not None:
                    update_payload["status"] = ReminderStatus(status.value)
                if received_at is not None:
                    update_payload["received_at"] = received_at
                if increment_retry:
                    update_payload["retry_count"] = (reminder.retry_count or 0) + 1

                if not update_payload:
                    return

                update_data = ReminderUpdateInternal(**update_payload)
                await crud_reminders.update(
                    db=db,
                    object=update_data,
                    id=reminder.id,
                )
                updated = True
        except Exception as exc:  # pragma: no cover - defensive logging
            self.logger.bind(tag=TAG).exception(
                f"[Reminder] _update_reminder thất bại: {exc}"
            )
            raise
        if updated:
            self.logger.bind(tag=TAG).debug(
                f"[Reminder] Đã cập nhật reminder {reminder_id}"
            )

    def schedule_reminder(
        self,
        reminder: ReminderRead,
        device_id: str,
        mac_address: str,
    ) -> ReminderCreationResult:
        """Lên lịch reminder vào scheduler.

        Args:
            reminder: ReminderRead object (chứa agent_id)
            device_id: Device UUID (dùng cho check online/send message)
            mac_address: MAC address (dùng cho MQTT)
        """
        try:
            self.logger.bind(tag=TAG).debug(
                f"[Reminder] schedule_reminder: reminder_id={reminder.reminder_id}, agent_id={reminder.agent_id}, device_id={device_id}, mac={mac_address}"
            )
            tz = self.scheduler_service.timezone
            remind_at_local = reminder.remind_at_local
            if remind_at_local.tzinfo is None:
                remind_at_local = remind_at_local.replace(tzinfo=tz)
            else:
                remind_at_local = remind_at_local.astimezone(tz)

            payload = {
                "id": str(reminder.id),
                "reminder_id": reminder.reminder_id,
                "agent_id": reminder.agent_id,
                "device_id": device_id,
                "mac_address": mac_address,
                "content": reminder.content,
                "title": reminder.title or "",
                "metadata": reminder.reminder_metadata or {},
                "remind_at": reminder.remind_at.astimezone(timezone.utc).isoformat(),
                "remind_at_local": remind_at_local.isoformat(),
                "created_at": reminder.created_at.isoformat(),
            }

            self.scheduler_service.schedule(
                reminder.reminder_id, remind_at_local, payload
            )
            self.logger.bind(tag=TAG).debug(
                f"[Reminder] Đã push job vào scheduler cho {reminder.reminder_id}"
            )
            return ReminderCreationResult(
                reminder_id=reminder.reminder_id,
                remind_at=remind_at_local,
                payload=payload,
                reminder_db_id=str(reminder.id),
            )
        except Exception as exc:
            self.logger.bind(tag=TAG).exception(
                f"[Reminder] schedule_reminder thất bại: {exc}"
            )
            raise

    async def _on_reminder_due(self, payload: Dict[str, Any]) -> None:
        reminder_id = payload.get("reminder_id", "")
        agent_id = payload.get("agent_id", "")
        device_id = payload.get("device_id", "")
        mac_address = payload.get("mac_address", "")

        self.logger.bind(tag=TAG).debug(
            f"[Reminder] Job kích hoạt reminder_id={reminder_id}, agent={agent_id}, device={device_id}, mac={mac_address}"
        )

        # Build payload cho message - sử dụng notification format đơn giản
        reminder_message_payload = {
            "type": "notification",
            "useLLM": True,
            "title": payload.get("title", ""),
            "content": payload.get("content", ""),
        }

        # Check MQTT availability (sync method)
        mqtt_available = (
            self.mqtt_service.is_available() if self.mqtt_service else False
        )

        # Check device online status
        device_online = await is_device_online(device_id)
        delivery_method = None
        delivery_sent = False

        try:
            if device_online:
                # Device online: Try WS first
                self.logger.bind(tag=TAG).debug(
                    f"[Reminder] Device {device_id} đang online, gửi qua WebSocket"
                )
                # Find ConnectionHandler từ active_connections
                active_connections = (
                    getattr(self.app_state, "active_connections", set())
                    if self.app_state
                    else set()
                )

                ws_sent = False
                for handler in active_connections:
                    # Match device bằng device_id
                    if str(handler.device_id) == str(device_id):
                        try:
                            loop = getattr(handler, "loop", None)
                            if loop is None or not loop.is_running():
                                continue
                            coro = self.notification_handler.handle(
                                handler, reminder_message_payload
                            )
                            asyncio.run_coroutine_threadsafe(coro, loop)
                            self.logger.bind(tag=TAG).info(
                                f"[Reminder] Gửi WS thành công cho device {device_id}, reminder_id={reminder_id}"
                            )
                            ws_sent = True
                            delivery_method = "WS"
                            delivery_sent = True
                            break
                        except Exception as ws_exc:
                            self.logger.bind(tag=TAG).warning(
                                f"[Reminder] Gửi WS thất bại cho device {device_id}: {ws_exc}"
                            )

                # WS không thành công, fallback to MQTT nếu có sẵn
                if not ws_sent and mqtt_available:
                    self.logger.bind(tag=TAG).debug(
                        f"[Reminder] WebSocket không khả dụng cho device {device_id}, fallback MQTT"
                    )
                    try:
                        # Build topic từ topic_base và mac_address
                        topic = f"{self.topic_base.rstrip('/')}/{mac_address}"
                        success = await self.mqtt_service.publish(
                            topic, reminder_message_payload
                        )
                        if success:
                            delivery_method = "MQTT"
                            delivery_sent = True
                    except Exception as mqtt_exc:
                        self.logger.bind(tag=TAG).warning(
                            f"[Reminder] Gửi MQTT thất bại: {mqtt_exc}"
                        )

                # Nếu vẫn chưa gửi được và MQTT không khả dụng, log warning
                if not delivery_sent and not mqtt_available:
                    self.logger.bind(tag=TAG).warning(
                        f"[Reminder] Device {device_id} online nhưng WebSocket không khả dụng, MQTT cũng không có kết nối"
                    )
            else:
                # Device offline: Chỉ gửi MQTT nếu khả dụng
                if mqtt_available:
                    self.logger.bind(tag=TAG).debug(
                        f"[Reminder] Device {device_id} đang offline, gửi qua MQTT"
                    )
                    try:
                        # Build topic từ topic_base và mac_address
                        topic = f"{self.topic_base.rstrip('/')}/{mac_address}"
                        success = await self.mqtt_service.publish(
                            topic, reminder_message_payload
                        )
                        if success:
                            delivery_method = "MQTT"
                            delivery_sent = True
                    except Exception as mqtt_exc:
                        self.logger.bind(tag=TAG).error(
                            f"[Reminder] Gửi MQTT thất bại: {mqtt_exc}"
                        )
                else:
                    self.logger.bind(tag=TAG).warning(
                        f"[Reminder] Device {device_id} offline và MQTT không có kết nối, không thể gửi reminder {reminder_id}"
                    )

            # Update status based on delivery result
            if delivery_sent:
                await self._update_reminder(
                    reminder_id, status=ReminderStatus.DELIVERED
                )
                self.logger.bind(tag=TAG).info(
                    f"[Reminder] Đã gửi reminder {reminder_id} thành công ({delivery_method})"
                )
            else:
                # Không gửi được, cập nhật status thành FAILED
                await self._update_reminder(
                    reminder_id,
                    status=ReminderStatus.FAILED,
                    increment_retry=True,
                )
                self.logger.bind(tag=TAG).error(
                    f"[Reminder] Không thể gửi reminder {reminder_id} - device offline và MQTT không khả dụng"
                )
                raise RuntimeError(
                    f"Không thể gửi reminder {reminder_id}: device offline và MQTT không khả dụng"
                )

        except Exception as exc:
            self.logger.bind(tag=TAG).error(
                f"[Reminder] Gửi reminder {reminder_id} thất bại ({delivery_method}): {exc}"
            )
            try:
                # Chỉ cập nhật FAILED nếu chưa được cập nhật
                if not delivery_sent:
                    await self._update_reminder(
                        reminder_id,
                        status=ReminderStatus.FAILED,
                        increment_retry=True,
                    )
            except Exception as update_exc:
                self.logger.bind(tag=TAG).warning(
                    f"[Reminder] Không thể cập nhật trạng thái FAILED cho {reminder_id}: {update_exc}"
                )
            raise

    async def consume_reminder(
        self, device_id: str, reminder_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Lấy reminder payload từ database.

        Args:
            device_id: Device ID để xác thực quyền truy cập
            reminder_id: Reminder ID cần lấy

        Returns:
            Reminder payload nếu tồn tại và thuộc device, None nếu không
        """
        try:
            async with local_session() as db:
                reminder = await crud_reminders.get(
                    db=db,
                    reminder_id=reminder_id,
                    is_deleted=False,
                    schema_to_select=ReminderRead,
                    return_as_model=True,
                )
                if reminder is None:
                    self.logger.bind(tag=TAG).debug(
                        f"[Reminder] Không tìm thấy reminder {reminder_id}"
                    )
                    return None

                # Xác thực rằng reminder thuộc agent_id (query qua agent)
                # Note: ReminderRead chỉ có agent_id, không có device_id
                # Validation có thể được thực hiện ở API layer (check agent ownership)

                # Build payload từ DB record
                payload = {
                    "id": str(reminder.id),
                    "reminder_id": reminder.reminder_id,
                    "agent_id": str(reminder.agent_id),
                    "content": reminder.content,
                    "title": reminder.title or "",
                    "metadata": reminder.reminder_metadata or {},
                    "remind_at": reminder.remind_at.isoformat(),
                    "remind_at_local": reminder.remind_at_local.isoformat(),
                    "created_at": reminder.created_at.isoformat(),
                }
                self.logger.bind(tag=TAG).debug(
                    f"[Reminder] consume_reminder thành công cho {reminder_id}"
                )
                return payload
        except Exception as exc:
            self.logger.bind(tag=TAG).exception(
                f"[Reminder] consume_reminder thất bại cho {reminder_id}: {exc}"
            )
            raise
