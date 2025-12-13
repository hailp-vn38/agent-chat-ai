from __future__ import annotations

from datetime import timedelta, timezone
from typing import Any

try:
    from zoneinfo import ZoneInfo  # Python 3.9+
except ImportError:  # pragma: no cover - fallback for older Python
    ZoneInfo = None  # type: ignore


def resolve_timezone(value: Any) -> timezone:
    """Chuyển chuỗi tz hoặc offset sang timezone.

    Ưu tiên tên tz IANA (ví dụ: 'Asia/Ho_Chi_Minh'), fallback sang định dạng offset '+07:00' hoặc số.
    """
    if isinstance(value, timezone):
        return value

    if value is None:
        return timezone.utc

    tz_str = str(value).strip()
    if not tz_str or tz_str.lower() == "utc":
        return timezone.utc

    # Thử解析 tên tz IANA
    if ZoneInfo is not None:
        try:
            return ZoneInfo(tz_str)
        except Exception:
            pass

    # Fallback offset dạng +7, +07:00, -420 (phút)
    try:
        sign = 1
        offset_value = tz_str

        if offset_value.startswith("-"):
            sign = -1
            offset_value = offset_value[1:]
        elif offset_value.startswith("+"):
            offset_value = offset_value[1:]

        hours = 0
        minutes = 0

        if ":" in offset_value:
            hours_str, minutes_str = offset_value.split(":", 1)
            hours = int(hours_str)
            minutes = int(minutes_str)
        else:
            if offset_value.isdigit():
                hours = int(offset_value)
            else:
                # Có thể cung cấp offset theo phút (VD: 420)
                minutes = int(offset_value)
                return timezone(sign * timedelta(minutes=minutes))

        delta = timedelta(hours=sign * hours, minutes=sign * minutes)
        return timezone(delta)
    except Exception:
        return timezone.utc
