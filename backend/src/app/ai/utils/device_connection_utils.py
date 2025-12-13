"""
Device Connection Utilities
Các hàm tiện ích để kiểm tra và quản lý trạng thái kết nối device qua Redis
"""

from typing import List
from app.core.logger import setup_logging
from app.ai.utils.cache import async_cache_manager, CacheType

logger = setup_logging()
TAG = __name__


async def is_device_online(device_id: str) -> bool:
    """
    Kiểm tra device có đang kết nối WebSocket hay không.

    Args:
        device_id: UUID của device

    Returns:
        True nếu device đang online, False nếu offline

    Example:
        >>> is_online = await is_device_online("device-uuid-123")
        >>> if is_online:
        >>>     print("Device is online!")
    """
    try:
        # Preferred key (new): device:{device_id}:status on CacheType.DEVICE
        status = await async_cache_manager.get(
            cache_type=CacheType.DEVICE, key=f"{device_id}:status"
        )

        # Backward compatibility: old key on CacheType.CONFIG
        if status is None:
            status = await async_cache_manager.get(
                cache_type=CacheType.CONFIG, key=f"device:{device_id}:status"
            )

        is_online = status is not None
        logger.bind(tag=TAG).debug(
            f"Device {device_id}: {'🟢 ONLINE' if is_online else '🔴 OFFLINE'}"
        )
        return is_online
    except Exception as e:
        logger.bind(tag=TAG).error(f"Lỗi kiểm tra trạng thái device {device_id}: {e}")
        return False


async def get_all_online_devices() -> List[str]:
    """
    Lấy danh sách tất cả device đang kết nối.

    Returns:
        List của device_id đang online

    Example:
        >>> online_devices = await get_all_online_devices()
        >>> print(f"Online devices: {online_devices}")  # ['uuid-1', 'uuid-2', ...]
    """
    try:
        # Scan pattern: device:*:status
        cursor = 0
        online_devices = []

        # Sử dụng redis client từ async_get_redis
        from app.core.utils.cache import async_get_redis

        async for redis_client in async_get_redis():
            while True:
                cursor, keys = await redis_client.scan(
                    cursor, match="config:device:*:status", count=100
                )

                if keys:
                    # Extract device_id từ key format: config:device:{device_id}:status
                    for key in keys:
                        key_str = key.decode() if isinstance(key, bytes) else key
                        parts = key_str.split(":")
                        if len(parts) >= 3:
                            device_id = parts[2]
                            online_devices.append(device_id)

                if cursor == 0:
                    break

        logger.bind(tag=TAG).info(
            f"Tìm thấy {len(online_devices)} device(s) đang online"
        )
        return online_devices

    except Exception as e:
        logger.bind(tag=TAG).error(f"Lỗi lấy danh sách device online: {e}")
        return []


async def count_online_devices() -> int:
    """
    Đếm tổng số device đang kết nối.

    Returns:
        Số lượng device online

    Example:
        >>> count = await count_online_devices()
        >>> print(f"Total online: {count}")  # Total online: 5
    """
    devices = await get_all_online_devices()
    return len(devices)


async def refresh_device_connection(device_id: str, ttl: int = 300) -> bool:
    """
    Làm mới TTL của device connection (khi nhận heartbeat từ device).

    Args:
        device_id: UUID của device
        ttl: Thời gian timeout (default 5 phút)

    Returns:
        True nếu thành công

    Example:
        >>> success = await refresh_device_connection("device-uuid-123")
        >>> if success:
        >>>     print("Connection refreshed!")
    """
    try:
        # Re-set value để refresh TTL
        await async_cache_manager.set(
            cache_type=CacheType.CONFIG,
            key=f"device:{device_id}:status",
            value="connected",
            ttl=ttl,
        )
        logger.bind(tag=TAG).debug(f"🔄 Làm mới TTL cho device {device_id} ({ttl}s)")
        return True
    except Exception as e:
        logger.bind(tag=TAG).error(f"Lỗi làm mới connection device {device_id}: {e}")
        return False


async def force_disconnect_device(device_id: str) -> bool:
    """
    Cưỡng bức ngắt kết nối device (xoá khỏi Redis).
    Dùng cho admin operations hoặc cleanup.

    Args:
        device_id: UUID của device

    Returns:
        True nếu xoá thành công, False nếu không tìm thấy

    Example:
        >>> deleted = await force_disconnect_device("device-uuid-123")
        >>> if deleted:
        >>>     print("Device forced offline!")
    """
    try:
        deleted = await async_cache_manager.delete(
            cache_type=CacheType.CONFIG, key=f"device:{device_id}:status"
        )
        if deleted:
            logger.bind(tag=TAG).info(f"⚠️  Device {device_id} đã bị cưỡng bức ngắt")
        else:
            logger.bind(tag=TAG).warning(
                f"Device {device_id} không tìm thấy trên Redis"
            )
        return deleted
    except Exception as e:
        logger.bind(tag=TAG).error(f"Lỗi cưỡng bức ngắt device {device_id}: {e}")
        return False


async def get_device_connection_status(device_id: str) -> dict:
    """
    Lấy trạng thái chi tiết của device connection.

    Args:
        device_id: UUID của device

    Returns:
        Dict chứa thông tin kết nối

    Example:
        >>> status = await get_device_connection_status("device-uuid-123")
        >>> print(status)
        >>> # {
        >>> #     "device_id": "device-uuid-123",
        >>> #     "is_online": True,
        >>> #     "status": "connected",
        >>> #     "cached": True
        >>> # }
    """
    try:
        status_value = await async_cache_manager.get(
            cache_type=CacheType.CONFIG, key=f"device:{device_id}:status"
        )

        return {
            "device_id": device_id,
            "is_online": status_value is not None,
            "status": status_value or "offline",
            "cached": status_value is not None,
        }
    except Exception as e:
        logger.bind(tag=TAG).error(f"Lỗi lấy trạng thái device {device_id}: {e}")
        return {
            "device_id": device_id,
            "is_online": False,
            "status": "error",
            "cached": False,
            "error": str(e),
        }


async def clear_all_device_connections() -> int:
    """
    Xoá tất cả device connections từ Redis (cleanup).
    Cần dùng cẩn thận!

    Returns:
        Số lượng device bị xoá

    Example:
        >>> deleted_count = await clear_all_device_connections()
        >>> print(f"Deleted {deleted_count} connections")
    """
    try:
        await async_cache_manager.clear(cache_type=CacheType.CONFIG)
        logger.bind(tag=TAG).warning("⚠️  Tất cả device connections đã bị xoá!")
        return len(await get_all_online_devices())
    except Exception as e:
        logger.bind(tag=TAG).error(f"Lỗi khi xoá tất cả connections: {e}")
        return 0
