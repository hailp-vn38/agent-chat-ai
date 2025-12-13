import asyncio
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

CURRENT_FILE = Path(__file__).resolve()
SRC_DIR = CURRENT_FILE.parents[3]
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from app.config.config_loader import load_config
from app.config.settings import (
    ReminderSettings,
    ReminderMQTTSettings,
    ReminderSchedulerSettings,
    ReminderJobStoreSettings,
    ServerSettings,
)
from uuid import uuid4

from app.schemas.reminder import ReminderRead
from app.models.reminder import ReminderStatus
from app.services.reminder_service import ReminderService


description = "Kiểm thử logic nhắc nhở (scheduler + repository)"


async def run_reminder_test():
    """Tạo lời nhắc giả lập và xác nhận chu trình scheduler"""
    job_store_dir = Path("tmp/perf_reminder_jobs")
    job_store_dir.mkdir(parents=True, exist_ok=True)

    config = load_config()

    reminder_settings = ReminderSettings(
        mqtt=ReminderMQTTSettings(tts_mqtt_url=""),
        scheduler=ReminderSchedulerSettings(
            job_store=ReminderJobStoreSettings(
                folder=str(job_store_dir), filename="reminder_test.sqlite"
            )
        ),
    )
    server_settings = ServerSettings(**config.get("server", {}))

    reminder_service = ReminderService(reminder_settings, server_settings)
    reminder_service.scheduler_service.start()

    triggered = asyncio.Event()
    published_payloads = []

    async def fake_publish(device_id, payload):
        published_payloads.append((device_id, payload))
        triggered.set()

    reminder_service.mqtt_service.publish = fake_publish  # type: ignore[assignment]

    remind_at = datetime.now(reminder_service.scheduler_service.timezone) + timedelta(
        seconds=2
    )

    reminder_record = ReminderRead(
        id=uuid4(),
        reminder_id=uuid4().hex,
        device_id=uuid4(),
        content="Đã đến giờ uống nước!",
        title="Nhắc uống nước",
        remind_at=remind_at.astimezone(timezone.utc),
        remind_at_local=remind_at,
        created_at=datetime.now(timezone.utc),
        status=ReminderStatus.PENDING,
        reminder_metadata={"test": True},
        received_at=None,
        retry_count=0,
    )

    result = reminder_service.schedule_reminder(reminder_record, "tester-device")

    print(f"Đã lên lịch reminder {result.reminder_id} lúc {result.remind_at}")

    try:
        await asyncio.wait_for(triggered.wait(), timeout=10)
    except asyncio.TimeoutError:
        raise RuntimeError("Reminder không được kích hoạt trong thời gian chờ")

    payloads = [payload for _, payload in published_payloads]
    if not payloads:
        raise RuntimeError("Không nhận được payload MQTT giả lập")

    reminder_payload = await reminder_service.consume_reminder(
        "tester-device", result.reminder_id
    )
    if not reminder_payload:
        raise RuntimeError("Không tìm thấy dữ liệu reminder trong repository")

    print("Payload MQTT:", payloads[0])
    print("Dữ liệu lưu trữ:", reminder_payload)

    await reminder_service.shutdown()
    print("Kiểm thử hoàn tất thành công.")


if __name__ == "__main__":
    asyncio.run(run_reminder_test())
