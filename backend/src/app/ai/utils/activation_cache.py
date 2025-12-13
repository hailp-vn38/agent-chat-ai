"""Activation code cache utilities for device registration and binding.

Pattern: Helper functions for managing one-time activation codes stored in Redis.
TTL: 24 hours (86400 seconds)
Key format: activation:{code} -> {mac_address}
"""

from typing import Optional

from redis.asyncio import Redis

from app.core.exceptions.cache_exceptions import MissingClientError
from app.core.logger import get_logger

logger = get_logger(__name__)

# Constants
ACTIVATION_TTL = 86400  # 24 hours
ACTIVATION_PREFIX = "activation"


async def store_activation_code(
    redis_client: Redis, mac_address: str, code: str, ttl: int = ACTIVATION_TTL
) -> None:
    """Store activation code mapped to MAC address in Redis.

    Parameters
    ----------
    redis_client : Redis
        Redis client instance
    mac_address : str
        Device MAC address (AA:BB:CC:DD:EE:FF format)
    code : str
        6-digit activation code
    ttl : int
        Time-to-live in seconds (default: 86400 = 24 hours)

    Raises
    ------
    MissingClientError
        If redis_client is None or not initialized

    Example
    -------
    await store_activation_code(redis_client, "AA:BB:CC:DD:EE:FF", "123456")
    # Stores in Redis: activation:123456 -> "AA:BB:CC:DD:EE:FF"
    """
    if redis_client is None:
        logger.error("Redis client not initialized for activation code storage")
        raise MissingClientError("Redis client is not initialized")

    key = f"{ACTIVATION_PREFIX}:{code}"
    try:
        await redis_client.set(key, mac_address, ex=ttl)
        logger.info(
            f"Stored activation code {code} for MAC {mac_address} (TTL: {ttl}s)"
        )
    except Exception as e:
        logger.error(f"Failed to store activation code {code}: {e}")
        raise


async def get_mac_from_code(redis_client: Redis, code: str) -> Optional[str]:
    """Retrieve MAC address from activation code.

    Parameters
    ----------
    redis_client : Redis
        Redis client instance
    code : str
        6-digit activation code

    Returns
    -------
    Optional[str]
        MAC address if code exists and is valid, None otherwise

    Raises
    ------
    MissingClientError
        If redis_client is None or not initialized

    Example
    -------
    mac = await get_mac_from_code(redis_client, "123456")
    # Returns: "AA:BB:CC:DD:EE:FF" or None
    """
    if redis_client is None:
        logger.error("Redis client not initialized for activation code retrieval")
        raise MissingClientError("Redis client is not initialized")

    key = f"{ACTIVATION_PREFIX}:{code}"
    try:
        mac_address = await redis_client.get(key)
        if mac_address is None:
            logger.warning(f"Activation code {code} not found or expired")
            return None

        mac_str = (
            mac_address.decode() if isinstance(mac_address, bytes) else mac_address
        )
        logger.debug(f"Retrieved MAC {mac_str} for activation code {code}")
        return mac_str
    except Exception as e:
        logger.error(f"Failed to retrieve activation code {code}: {e}")
        raise


async def delete_activation_code(redis_client: Redis, code: str) -> None:
    """Delete activation code from Redis after use.

    Parameters
    ----------
    redis_client : Redis
        Redis client instance
    code : str
        6-digit activation code to delete

    Raises
    ------
    MissingClientError
        If redis_client is None or not initialized

    Example
    -------
    await delete_activation_code(redis_client, "123456")
    """
    if redis_client is None:
        logger.error("Redis client not initialized for activation code deletion")
        raise MissingClientError("Redis client is not initialized")

    key = f"{ACTIVATION_PREFIX}:{code}"
    try:
        result = await redis_client.delete(key)
        if result > 0:
            logger.info(f"Deleted activation code {code}")
        else:
            logger.debug(
                f"Activation code {code} not found (already expired or deleted)"
            )
    except Exception as e:
        logger.error(f"Failed to delete activation code {code}: {e}")
        raise


# ============ OTA Device Data Cache ============


OTA_DEVICE_DATA_PREFIX = "ota_device_data"
OTA_DEVICE_DATA_TTL = 86400  # 24 hours


async def store_ota_device_data(
    redis_client: Redis,
    mac_address: str,
    device_data: dict,
    ttl: int = OTA_DEVICE_DATA_TTL,
) -> None:
    """Store OTA device information data in Redis.

    Stores complete device information from OTA request for later retrieval
    during device binding process.

    Parameters
    ----------
    redis_client : Redis
        Redis client instance
    mac_address : str
        Device MAC address (AA:BB:CC:DD:EE:FF format)
    device_data : dict
        Complete device information from OTA POST request
    ttl : int
        Time-to-live in seconds (default: 86400 = 24 hours)

    Raises
    ------
    MissingClientError
        If redis_client is None or not initialized

    Example
    -------
    await store_ota_device_data(
        redis_client,
        "AA:BB:CC:DD:EE:FF",
        {"version": 2, "language": "vi", ...}
    )
    # Stores in Redis: ota_device_data:AA:BB:CC:DD:EE:FF -> JSON data
    """
    if redis_client is None:
        logger.error("Redis client not initialized for OTA device data storage")
        raise MissingClientError("Redis client is not initialized")

    import json

    key = f"{OTA_DEVICE_DATA_PREFIX}:{mac_address}"
    try:
        device_data_json = json.dumps(device_data)
        await redis_client.set(key, device_data_json, ex=ttl)
        logger.info(f"Stored OTA device data for MAC {mac_address} (TTL: {ttl}s)")
    except Exception as e:
        logger.error(f"Failed to store OTA device data for MAC {mac_address}: {e}")
        raise


async def get_ota_device_data(redis_client: Redis, mac_address: str) -> Optional[dict]:
    """Retrieve OTA device data from Redis.

    Parameters
    ----------
    redis_client : Redis
        Redis client instance
    mac_address : str
        Device MAC address (AA:BB:CC:DD:EE:FF format)

    Returns
    -------
    Optional[dict]
        Device data if found, None otherwise

    Raises
    ------
    MissingClientError
        If redis_client is None or not initialized

    Example
    -------
    device_data = await get_ota_device_data(redis_client, "AA:BB:CC:DD:EE:FF")
    # Returns: {"version": 2, "language": "vi", ...} or None
    """
    if redis_client is None:
        logger.error("Redis client not initialized for OTA device data retrieval")
        raise MissingClientError("Redis client is not initialized")

    import json

    key = f"{OTA_DEVICE_DATA_PREFIX}:{mac_address}"
    try:
        device_data_json = await redis_client.get(key)
        if device_data_json is None:
            logger.warning(
                f"OTA device data for MAC {mac_address} not found or expired"
            )
            return None

        device_data_str = (
            device_data_json.decode()
            if isinstance(device_data_json, bytes)
            else device_data_json
        )
        device_data = json.loads(device_data_str)
        logger.debug(f"Retrieved OTA device data for MAC {mac_address}")
        return device_data
    except Exception as e:
        logger.error(f"Failed to retrieve OTA device data for MAC {mac_address}: {e}")
        raise


# ============ Device Activation Bundle (Code + OTA Data) ============


async def store_device_activation_data(
    redis_client: Redis,
    mac_address: str,
    activation_code: str,
    device_data: dict,
    ttl: int = ACTIVATION_TTL,
) -> None:
    """Store activation code and device data atomically under mac_address key.

    Stores both activation code and complete OTA device data in a single
    Redis operation, using mac_address as the primary key. This ensures
    consistency and reduces the number of Redis operations.

    Parameters
    ----------
    redis_client : Redis
        Redis client instance
    mac_address : str
        Device MAC address (AA:BB:CC:DD:EE:FF format)
    activation_code : str
        6-digit activation code
    device_data : dict
        Complete device information from OTA POST request
    ttl : int
        Time-to-live in seconds (default: 86400 = 24 hours)

    Raises
    ------
    MissingClientError
        If redis_client is None or not initialized

    Example
    -------
    await store_device_activation_data(
        redis_client,
        "AA:BB:CC:DD:EE:FF",
        "123456",
        {"version": 2, "language": "vi", ...}
    )
    # Stores in Redis: device_activation:AA:BB:CC:DD:EE:FF -> {code, device_data}
    """
    if redis_client is None:
        logger.error("Redis client not initialized for device activation data storage")
        raise MissingClientError("Redis client is not initialized")

    import json

    key = f"device_activation:{mac_address}"
    activation_payload = {
        "code": activation_code,
        "device_data": device_data,
    }

    try:
        payload_json = json.dumps(activation_payload)
        await redis_client.set(key, payload_json, ex=ttl)
        logger.info(
            f"Stored activation data for MAC {mac_address} with code {activation_code} (TTL: {ttl}s)"
        )
    except Exception as e:
        logger.error(
            f"Failed to store device activation data for MAC {mac_address}: {e}"
        )
        raise


async def get_device_activation_data(
    redis_client: Redis, mac_address: str
) -> Optional[dict]:
    """Retrieve activation code and device data by mac_address.

    Parameters
    ----------
    redis_client : Redis
        Redis client instance
    mac_address : str
        Device MAC address (AA:BB:CC:DD:EE:FF format)

    Returns
    -------
    Optional[dict]
        Dictionary with keys 'code' and 'device_data', or None if not found

    Example
    -------
    activation_data = await get_device_activation_data(redis_client, "AA:BB:CC:DD:EE:FF")
    # Returns: {"code": "123456", "device_data": {...}} or None
    """
    if redis_client is None:
        logger.error("Redis client not initialized for device activation data retrieval")
        raise MissingClientError("Redis client is not initialized")

    import json

    key = f"device_activation:{mac_address}"
    try:
        data_json = await redis_client.get(key)
        if data_json is None:
            logger.debug(f"Device activation data for MAC {mac_address} not found")
            return None

        data_str = data_json.decode() if isinstance(data_json, bytes) else data_json
        activation_data = json.loads(data_str)
        logger.debug(f"Retrieved device activation data for MAC {mac_address}")
        return activation_data
    except Exception as e:
        logger.error(
            f"Failed to retrieve device activation data for MAC {mac_address}: {e}"
        )
        raise


async def delete_device_activation_data(redis_client: Redis, mac_address: str) -> None:
    """Delete device activation data (code + OTA data) from Redis.

    Parameters
    ----------
    redis_client : Redis
        Redis client instance
    mac_address : str
        Device MAC address (AA:BB:CC:DD:EE:FF format)

    Example
    -------
    await delete_device_activation_data(redis_client, "AA:BB:CC:DD:EE:FF")
    """
    if redis_client is None:
        logger.error("Redis client not initialized for device activation data deletion")
        raise MissingClientError("Redis client is not initialized")

    key = f"device_activation:{mac_address}"
    try:
        result = await redis_client.delete(key)
        if result > 0:
            logger.info(f"Deleted device activation data for MAC {mac_address}")
        else:
            logger.debug(f"Device activation data for MAC {mac_address} not found")
    except Exception as e:
        logger.error(f"Failed to delete device activation data for MAC {mac_address}: {e}")
        raise
