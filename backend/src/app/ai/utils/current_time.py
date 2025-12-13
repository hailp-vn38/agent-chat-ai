"""
Mô-đun tiện ích thời gian
Cung cấp chức năng lấy thời gian thống nhất
"""

from datetime import datetime

WEEKDAY_MAP = {
    "Monday": "Thứ Hai",
    "Tuesday": "Thứ Ba",
    "Wednesday": "Thứ Tư",
    "Thursday": "Thứ Năm",
    "Friday": "Thứ Sáu",
    "Saturday": "Thứ Bảy",
    "Sunday": "Chủ Nhật",
}


def get_current_time() -> str:
    """
    Lấy chuỗi thời gian hiện tại (định dạng: HH:MM)
    """
    return datetime.now().strftime("%H:%M")


def get_current_date() -> str:
    """
    Lấy chuỗi ngày hôm nay (định dạng: YYYY-MM-DD)
    """
    return datetime.now().strftime("%Y-%m-%d")


def get_current_weekday() -> str:
    """
    Lấy hôm nay là thứ mấy
    """
    now = datetime.now()
    return WEEKDAY_MAP[now.strftime("%A")]


def get_current_time_info() -> tuple:
    """
    Lấy thông tin thời gian hiện tại
    Trả về: (chuỗi thời gian hiện tại, ngày hôm nay, thứ trong tuần, ngày âm lịch)
    """
    current_time = get_current_time()
    today_date = get_current_date()
    today_weekday = get_current_weekday()
    
    return current_time, today_date, today_weekday
