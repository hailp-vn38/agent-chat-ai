import functools
import json
import re
from collections.abc import AsyncGenerator, Callable
from typing import Any
from enum import Enum
from abc import ABC, abstractmethod

from fastapi import Request
from fastapi.encoders import jsonable_encoder
from redis.asyncio import ConnectionPool, Redis

from app.core.exceptions.cache_exceptions import (
    CacheIdentificationInferenceError,
    InvalidRequestError,
    MissingClientError,
)


# ============ Cache Key Management ============


class CacheKey(str, Enum):
    """
    Centralized cache key definitions with pattern support.

    Pattern: {prefix}:{identifier}
    Example: activation:AA:BB:CC:DD:EE:FF

    Usage:
        await cache_manager.set(CacheKey.DEVICE_ACTIVATION, mac_address, data)
        data = await cache_manager.get(CacheKey.DEVICE_ACTIVATION, mac_address)
    """

    # Device activation & OTA
    DEVICE_ACTIVATION = "device_activation"  # device_activation:{mac_address}
    OTA_DEVICE_DATA = "ota_device_data"  # ota_device_data:{mac_address}
    ACTIVATION_CODE = "activation"  # activation:{code} -> mac_address

    # User & Auth
    USER_CACHE = "user"  # user:{user_id}
    USER_PERMISSIONS = "user_permissions"  # user_permissions:{user_id}
    AUTH_TOKEN = "auth_token"  # auth_token:{token}

    # Agent & Device
    AGENT_CACHE = "agent"  # agent:{agent_id}
    DEVICE_CACHE = "device"  # device:{device_id}
    DEVICE_BY_MAC = (
        "device_by_mac"  # device_by_mac:{mac_address} - Device metadata (auth info)
    )

    # Session & Validation
    DEVICE_VALIDATION = "device_validated"  # device_validated:{mac_address}
    SESSION_CACHE = "session"  # session:{session_id}

    def format_key(self, *identifiers: str) -> str:
        """
        Format cache key with identifiers.

        Args:
            *identifiers: Variable number of identifiers to append

        Returns:
            str: Formatted cache key like "prefix:id1:id2:id3"

        Example:
            CacheKey.DEVICE_ACTIVATION.format_key(mac_address)
            → "device_activation:AA:BB:CC:DD:EE:FF"
        """
        parts = [self.value] + list(identifiers)
        return ":".join(parts)

    def pattern(self) -> str:
        """Get wildcard pattern for this key prefix."""
        return f"{self.value}:*"


# ============ Cache Manager Base Class ============


class BaseCacheManager(ABC):
    """
    Abstract base class for cache management.

    Provides type-safe interface for get/set/delete operations.
    Can be extended for different cache backends (Redis, Memcached, etc.)
    """

    @abstractmethod
    async def get(self, key: CacheKey | str, *identifiers: str) -> dict | None:
        """Get value from cache."""
        pass

    @abstractmethod
    async def set(
        self,
        key: CacheKey | str,
        value: dict | Any,
        *identifiers: str,
        ttl: int | None = None,
    ) -> None:
        """Set value in cache with optional TTL."""
        pass

    @abstractmethod
    async def delete(self, key: CacheKey | str, *identifiers: str) -> None:
        """Delete key from cache."""
        pass

    @abstractmethod
    async def delete_pattern(self, pattern: str) -> None:
        """Delete all keys matching pattern."""
        pass

    @abstractmethod
    async def exists(self, key: CacheKey | str, *identifiers: str) -> bool:
        """Check if key exists in cache."""
        pass

    def _build_key(self, key: CacheKey | str, *identifiers: str) -> str:
        """Build full cache key."""
        if isinstance(key, CacheKey):
            return key.format_key(*identifiers)
        else:
            if identifiers:
                return f"{key}:{':'.join(identifiers)}"
            return key


# ============ Redis Cache Manager Implementation ============


class RedisCacheManager(BaseCacheManager):
    """
    Redis-based cache manager with JSON serialization.

    Features:
    - Type-safe key management via CacheKey enum
    - Automatic JSON serialization/deserialization
    - TTL support
    - Pattern-based deletion
    - Error handling and logging
    """

    def __init__(self, redis_client: Redis, default_ttl: int = 86400):
        """
        Initialize Redis cache manager.

        Args:
            redis_client: Redis async client instance
            default_ttl: Default time-to-live in seconds (default: 24h)
        """
        self.redis = redis_client
        self.default_ttl = default_ttl

    async def get(self, key: CacheKey | str, *identifiers: str) -> dict | None:
        """
        Get value from cache and deserialize from JSON.

        Args:
            key: CacheKey enum or string key
            *identifiers: Variable identifiers for the key

        Returns:
            dict: Deserialized value or None if not found
        """
        try:
            cache_key = self._build_key(key, *identifiers)
            value = await self.redis.get(cache_key)

            if value is None:
                return None

            # Decode bytes to string if needed
            value_str = value.decode() if isinstance(value, bytes) else value
            return json.loads(value_str)

        except json.JSONDecodeError as e:
            raise ValueError(f"Failed to deserialize cache value for key {key}: {e}")
        except Exception as e:
            raise RuntimeError(f"Cache get error for key {key}: {e}")

    async def set(
        self,
        key: CacheKey | str,
        value: dict | Any,
        *identifiers: str,
        ttl: int | None = None,
    ) -> None:
        """
        Set value in cache with JSON serialization.

        Args:
            key: CacheKey enum or string key
            value: Value to cache (will be JSON serialized)
            *identifiers: Variable identifiers for the key
            ttl: Time-to-live in seconds (uses default if None)
        """
        try:
            cache_key = self._build_key(key, *identifiers)
            ttl = ttl or self.default_ttl

            # Serialize to JSON
            serialized = json.dumps(
                jsonable_encoder(value),
                default=str,
            )

            await self.redis.set(cache_key, serialized, ex=ttl)

        except json.JSONEncodeError as e:
            raise ValueError(f"Failed to serialize cache value for key {key}: {e}")
        except Exception as e:
            raise RuntimeError(f"Cache set error for key {key}: {e}")

    async def delete(self, key: CacheKey | str, *identifiers: str) -> None:
        """Delete key from cache."""
        try:
            cache_key = self._build_key(key, *identifiers)
            await self.redis.delete(cache_key)
        except Exception as e:
            raise RuntimeError(f"Cache delete error for key {key}: {e}")

    async def delete_pattern(self, pattern: str) -> None:
        """Delete all keys matching pattern using SCAN."""
        try:
            cursor = 0
            while True:
                cursor, keys = await self.redis.scan(cursor, match=pattern, count=100)
                if keys:
                    await self.redis.delete(*keys)
                if cursor == 0:
                    break
        except Exception as e:
            raise RuntimeError(f"Cache delete pattern error for {pattern}: {e}")

    async def exists(self, key: CacheKey | str, *identifiers: str) -> bool:
        """Check if key exists in cache."""
        try:
            cache_key = self._build_key(key, *identifiers)
            exists = await self.redis.exists(cache_key)
            return bool(exists)
        except Exception as e:
            raise RuntimeError(f"Cache exists error for key {key}: {e}")

    async def clear_all(self) -> None:
        """Clear all cache (use with caution!)."""
        try:
            await self.redis.flushdb()
        except Exception as e:
            raise RuntimeError(f"Cache clear error: {e}")


pool: ConnectionPool | None = None
client: Redis | None = None


def _infer_resource_id(
    kwargs: dict[str, Any], resource_id_type: type | tuple[type, ...]
) -> int | str:
    """Infer the resource ID from a dictionary of keyword arguments.

    Parameters
    ----------
    kwargs: Dict[str, Any]
        A dictionary of keyword arguments.
    resource_id_type: Union[type, Tuple[type, ...]]
        The expected type of the resource ID, which can be integer (int) or a string (str).

    Returns
    -------
    Union[None, int, str]
        The inferred resource ID. If it cannot be inferred or does not match the expected type, it returns None.

    Note
    ----
        - When `resource_id_type` is `int`, the function looks for an argument with the key 'id'.
        - When `resource_id_type` is `str`, it attempts to infer the resource ID as a string.
    """
    resource_id: int | str | None = None
    for arg_name, arg_value in kwargs.items():
        if isinstance(arg_value, resource_id_type):
            if (resource_id_type is int) and ("id" in arg_name):
                resource_id = arg_value

            elif (resource_id_type is int) and ("id" not in arg_name):
                pass

            elif resource_id_type is str:
                resource_id = arg_value

    if resource_id is None:
        raise CacheIdentificationInferenceError

    return resource_id


def _extract_data_inside_brackets(input_string: str) -> list[str]:
    """Extract data inside curly brackets from a given string using regular expressions.

    Parameters
    ----------
    input_string: str
        The input string in which to find data enclosed within curly brackets.

    Returns
    -------
    List[str]
        A list of strings containing the data found inside the curly brackets within the input string.

    Example
    -------
    >>> _extract_data_inside_brackets("The {quick} brown {fox} jumps over the {lazy} dog.")
    ['quick', 'fox', 'lazy']
    """
    data_inside_brackets = re.findall(r"{(.*?)}", input_string)
    return data_inside_brackets


def _construct_data_dict(
    data_inside_brackets: list[str], kwargs: dict[str, Any]
) -> dict[str, Any]:
    """Construct a dictionary based on data inside brackets and keyword arguments.

    Parameters
    ----------
    data_inside_brackets: List[str]
        A list of keys inside brackets.
    kwargs: Dict[str, Any]
        A dictionary of keyword arguments.

    Returns
    -------
    Dict[str, Any]: A dictionary with keys from data_inside_brackets and corresponding values from kwargs.
    """
    data_dict = {}
    for key in data_inside_brackets:
        data_dict[key] = kwargs[key]
    return data_dict


def _format_prefix(prefix: str, kwargs: dict[str, Any]) -> str:
    """Format a prefix using keyword arguments.

    Parameters
    ----------
    prefix: str
        The prefix template to be formatted.
    kwargs: Dict[str, Any]
        A dictionary of keyword arguments.

    Returns
    -------
    str: The formatted prefix.
    """
    data_inside_brackets = _extract_data_inside_brackets(prefix)
    data_dict = _construct_data_dict(data_inside_brackets, kwargs)
    formatted_prefix = prefix.format(**data_dict)
    return formatted_prefix


def _format_extra_data(
    to_invalidate_extra: dict[str, str], kwargs: dict[str, Any]
) -> dict[str, Any]:
    """Format extra data based on provided templates and keyword arguments.

    This function takes a dictionary of templates and their associated values and a dictionary of keyword arguments.
    It formats the templates with the corresponding values from the keyword arguments and returns a dictionary
    where keys are the formatted templates and values are the associated keyword argument values.

    Parameters
    ----------
    to_invalidate_extra: Dict[str, str]
        A dictionary where keys are templates and values are the associated values.
    kwargs: Dict[str, Any]
        A dictionary of keyword arguments.

    Returns
    -------
        Dict[str, Any]: A dictionary where keys are formatted templates and values
        are associated keyword argument values.
    """
    formatted_extra = {}
    for prefix, id_template in to_invalidate_extra.items():
        formatted_prefix = _format_prefix(prefix, kwargs)
        id = _extract_data_inside_brackets(id_template)[0]
        formatted_extra[formatted_prefix] = kwargs[id]

    return formatted_extra


async def _delete_keys_by_pattern(pattern: str) -> None:
    """Delete keys from Redis that match a given pattern using the SCAN command.

    This function iteratively scans the Redis key space for keys that match a specific pattern
    and deletes them. It uses the SCAN command to efficiently find keys, which is more
    performance-friendly compared to the KEYS command, especially for large datasets.

    The function scans the key space in an iterative manner using a cursor-based approach.
    It retrieves a batch of keys matching the pattern on each iteration and deletes them
    until no matching keys are left.

    Parameters
    ----------
    pattern: str
        The pattern to match keys against. The pattern can include wildcards,
        such as '*' for matching any character sequence. Example: 'user:*'

    Notes
    -----
    - The SCAN command is used with a count of 100 to retrieve keys in batches.
      This count can be adjusted based on the size of your dataset and Redis performance.

    - The function uses the delete command to remove keys in bulk. If the dataset
      is extremely large, consider implementing additional logic to handle bulk deletion
      more efficiently.

    - Be cautious with patterns that could match a large number of keys, as deleting
      many keys simultaneously may impact the performance of the Redis server.
    """
    if client is None:
        return

    cursor = 0
    while True:
        cursor, keys = await client.scan(cursor, match=pattern, count=100)
        if keys:
            await client.delete(*keys)
        if cursor == 0:
            break


def cache(
    key_prefix: str,
    resource_id_name: Any = None,
    expiration: int = 3600,
    resource_id_type: type | tuple[type, ...] = int,
    to_invalidate_extra: dict[str, Any] | None = None,
    pattern_to_invalidate_extra: list[str] | None = None,
) -> Callable:
    """Cache decorator for FastAPI endpoints.

    This decorator enables caching the results of FastAPI endpoint functions to improve response times
    and reduce the load on the application by storing and retrieving data in a cache.

    Parameters
    ----------
    key_prefix: str
        A unique prefix to identify the cache key.
    resource_id_name: Any, optional
        The name of the resource ID argument in the decorated function. If provided, it is used directly;
        otherwise, the resource ID is inferred from the function's arguments.
    expiration: int, optional
        The expiration time for the cached data in seconds. Defaults to 3600 seconds (1 hour).
    resource_id_type: Union[type, Tuple[type, ...]], default int
        The expected type of the resource ID.
        This can be a single type (e.g., int) or a tuple of types (e.g., (int, str)).
        Defaults to int. This is used only if resource_id_name is not provided.
    to_invalidate_extra: Dict[str, Any] | None, optional
        A dictionary where keys are cache key prefixes and values are templates for cache key suffixes.
        These keys are invalidated when the decorated function is called with a method other than GET.
    pattern_to_invalidate_extra: List[str] | None, optional
        A list of string patterns for cache keys that should be invalidated when the decorated function is called.
        This allows for bulk invalidation of cache keys based on a matching pattern.

    Returns
    -------
    Callable
        A decorator function that can be applied to FastAPI endpoint functions.

    Example usage
    -------------

    ```python
    from fastapi import FastAPI, Request
    from my_module import cache  # Replace with your actual module and imports

    app = FastAPI()

    # Define a sample endpoint with caching
    @app.get("/sample/{resource_id}")
    @cache(key_prefix="sample_data", expiration=3600, resource_id_type=int)
    async def sample_endpoint(request: Request, resource_id: int):
        # Your endpoint logic here
        return {"data": "your_data"}
    ```

    This decorator caches the response data of the endpoint function using a unique cache key.
    The cached data is retrieved for GET requests, and the cache is invalidated for other types of requests.

    Advanced Example Usage
    -------------
    ```python
    from fastapi import FastAPI, Request
    from my_module import cache

    app = FastAPI()


    @app.get("/users/{user_id}/items")
    @cache(key_prefix="user_items", resource_id_name="user_id", expiration=1200)
    async def read_user_items(request: Request, user_id: int):
        # Endpoint logic to fetch user's items
        return {"items": "user specific items"}


    @app.put("/items/{item_id}")
    @cache(
        key_prefix="item_data",
        resource_id_name="item_id",
        to_invalidate_extra={"user_items": "{user_id}"},
        pattern_to_invalidate_extra=["user_*_items:*"],
    )
    async def update_item(request: Request, item_id: int, data: dict, user_id: int):
        # Update logic for an item
        # Invalidate both the specific item cache and all user-specific item lists
        return {"status": "updated"}
    ```

    In this example:
    - When reading user items, the response is cached under a key formed with 'user_items' prefix and 'user_id'.
    - When updating an item, the cache for this specific item (under 'item_data:item_id') and all caches with keys
      starting with 'user_{user_id}_items:' are invalidated. The `to_invalidate_extra` parameter specifically targets
      the cache for user-specific item lists, while `pattern_to_invalidate_extra` allows bulk invalidation of all keys
      matching the pattern 'user_*_items:*', covering all users.

    Note
    ----
    - resource_id_type is used only if resource_id is not passed.
    - `to_invalidate_extra` and `pattern_to_invalidate_extra` are used for cache invalidation on methods other than GET.
    - Using `pattern_to_invalidate_extra` can be resource-intensive on large datasets. Use it judiciously and
      consider the potential impact on Redis performance.
    """

    def wrapper(func: Callable) -> Callable:
        @functools.wraps(func)
        async def inner(request: Request, *args: Any, **kwargs: Any) -> Any:
            if client is None:
                raise MissingClientError

            if resource_id_name:
                resource_id = kwargs[resource_id_name]
            else:
                resource_id = _infer_resource_id(
                    kwargs=kwargs, resource_id_type=resource_id_type
                )

            formatted_key_prefix = _format_prefix(key_prefix, kwargs)
            cache_key = f"{formatted_key_prefix}:{resource_id}"
            if request.method == "GET":
                if (
                    to_invalidate_extra is not None
                    or pattern_to_invalidate_extra is not None
                ):
                    raise InvalidRequestError

                cached_data = await client.get(cache_key)
                if cached_data:
                    return json.loads(cached_data.decode())

            result = await func(request, *args, **kwargs)

            if request.method == "GET":
                serializable_data = jsonable_encoder(result)
                serialized_data = json.dumps(serializable_data)

                await client.set(cache_key, serialized_data)
                await client.expire(cache_key, expiration)

                return json.loads(serialized_data)

            else:
                await client.delete(cache_key)
                if to_invalidate_extra is not None:
                    formatted_extra = _format_extra_data(to_invalidate_extra, kwargs)
                    for prefix, id in formatted_extra.items():
                        extra_cache_key = f"{prefix}:{id}"
                        await client.delete(extra_cache_key)

                if pattern_to_invalidate_extra is not None:
                    for pattern in pattern_to_invalidate_extra:
                        formatted_pattern = _format_prefix(pattern, kwargs)
                        await _delete_keys_by_pattern(formatted_pattern + "*")

            return result

        return inner

    return wrapper


async def async_get_redis() -> AsyncGenerator[Redis, None]:
    """Get a Redis client from the pool for each request."""
    client = Redis(connection_pool=pool)
    try:
        yield client
    finally:
        await client.aclose()  # type: ignore


def get_cache_manager(redis_client: Redis | None = None) -> BaseCacheManager:
    """
    Get cache manager instance for dependency injection.

    Usage in FastAPI:
        cache: BaseCacheManager = Depends(get_cache_manager)

    Args:
        redis_client: Optional Redis client (uses global if not provided)

    Returns:
        BaseCacheManager: RedisCacheManager instance
    """
    if redis_client is None:
        if client is None:
            raise MissingClientError("Redis client not initialized")
        redis_client = client

    return RedisCacheManager(redis_client)
