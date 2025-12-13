"""
AsyncRedisCacheManager - Redis-backed cache manager with async interface
Thay thế GlobalCacheManager với Redis backend để hỗ trợ persistence và scaling
"""

import json
from typing import Any, Optional

from app.core.logger import setup_logging
from app.core.utils.cache import async_get_redis

from .config import CacheConfig, CacheType

logger = setup_logging()
TAG = __name__


class AsyncRedisCacheManager:
    """Async Redis-backed cache manager"""

    def __init__(self):
        self._logger = logger
        self._stats = {"hits": 0, "misses": 0, "errors": 0}

    def _get_cache_key(
        self, cache_type: CacheType, key: str, namespace: str = ""
    ) -> str:
        """Construct Redis key from cache_type, namespace, and key"""
        if namespace:
            return f"{cache_type.value}:{namespace}:{key}"
        return f"{cache_type.value}:{key}"

    async def get(
        self, cache_type: CacheType, key: str, namespace: str = ""
    ) -> Optional[Any]:
        """Get value from Redis cache

        Parameters
        ----------
        cache_type : CacheType
            Type of cache (WEATHER, INTENT, etc.)
        key : str
            Cache key
        namespace : str, optional
            Namespace for key isolation (e.g., device_id)

        Returns
        -------
        Optional[Any]
            Cached value or None if not found/expired
        """
        cache_key = self._get_cache_key(cache_type, key, namespace)

        try:
            async for redis_client in async_get_redis():
                cached_data = await redis_client.get(cache_key)

                if cached_data is None:
                    self._stats["misses"] += 1
                    return None

                # Deserialize JSON data
                value = json.loads(cached_data.decode("utf-8"))
                self._stats["hits"] += 1

                self._logger.bind(tag=TAG).debug(f"Cache HIT: {cache_key}")
                return value

        except json.JSONDecodeError as e:
            self._stats["errors"] += 1
            self._logger.bind(tag=TAG).error(
                f"Failed to deserialize cache data for {cache_key}: {e}"
            )
            return None
        except Exception as e:
            self._stats["errors"] += 1
            self._logger.bind(tag=TAG).error(f"Error getting cache {cache_key}: {e}")
            return None

    async def set(
        self,
        cache_type: CacheType,
        key: str,
        value: Any,
        ttl: Optional[float] = None,
        namespace: str = "",
    ) -> None:
        """Set value to Redis cache with TTL

        Parameters
        ----------
        cache_type : CacheType
            Type of cache
        key : str
            Cache key
        value : Any
            Value to cache (must be JSON serializable)
        ttl : Optional[float]
            Time-to-live in seconds. If None, use config default
        namespace : str, optional
            Namespace for key isolation
        """
        cache_key = self._get_cache_key(cache_type, key, namespace)
        config = CacheConfig.for_type(cache_type)

        # Determine effective TTL
        effective_ttl = ttl if ttl is not None else config.ttl

        try:
            # Serialize value to JSON
            serialized_value = json.dumps(value, ensure_ascii=False)

            async for redis_client in async_get_redis():
                await redis_client.set(cache_key, serialized_value)

                # Set expiration if TTL is specified
                if effective_ttl is not None:
                    await redis_client.expire(cache_key, int(effective_ttl))

                self._logger.bind(tag=TAG).debug(
                    f"Cache SET: {cache_key} (TTL: {effective_ttl}s)"
                )

        except (TypeError, ValueError) as e:
            self._stats["errors"] += 1
            self._logger.bind(tag=TAG).error(
                f"Failed to serialize value for {cache_key}: {e}"
            )
        except Exception as e:
            self._stats["errors"] += 1
            self._logger.bind(tag=TAG).error(f"Error setting cache {cache_key}: {e}")

    async def delete(
        self, cache_type: CacheType, key: str, namespace: str = ""
    ) -> bool:
        """Delete a key from cache

        Returns
        -------
        bool
            True if key was deleted, False if key didn't exist
        """
        cache_key = self._get_cache_key(cache_type, key, namespace)

        try:
            async for redis_client in async_get_redis():
                result = await redis_client.delete(cache_key)

                self._logger.bind(tag=TAG).debug(
                    f"Cache DELETE: {cache_key} (deleted: {result > 0})"
                )
                return result > 0

        except Exception as e:
            self._stats["errors"] += 1
            self._logger.bind(tag=TAG).error(f"Error deleting cache {cache_key}: {e}")
            return False

    async def clear(self, cache_type: CacheType, namespace: str = "") -> None:
        """Clear all keys for a cache type and namespace"""
        pattern = self._get_cache_key(cache_type, "*", namespace)

        try:
            async for redis_client in async_get_redis():
                cursor = 0
                deleted_count = 0

                while True:
                    cursor, keys = await redis_client.scan(
                        cursor, match=pattern, count=100
                    )

                    if keys:
                        deleted = await redis_client.delete(*keys)
                        deleted_count += deleted

                    if cursor == 0:
                        break

                self._logger.bind(tag=TAG).info(
                    f"Cache CLEAR: {pattern} (deleted {deleted_count} keys)"
                )

        except Exception as e:
            self._stats["errors"] += 1
            self._logger.bind(tag=TAG).error(f"Error clearing cache {pattern}: {e}")

    async def invalidate_pattern(
        self, cache_type: CacheType, pattern: str, namespace: str = ""
    ) -> int:
        """Invalidate cache keys matching pattern

        Returns
        -------
        int
            Number of keys deleted
        """
        search_pattern = self._get_cache_key(cache_type, f"*{pattern}*", namespace)

        try:
            async for redis_client in async_get_redis():
                cursor = 0
                deleted_count = 0

                while True:
                    cursor, keys = await redis_client.scan(
                        cursor, match=search_pattern, count=100
                    )

                    if keys:
                        deleted = await redis_client.delete(*keys)
                        deleted_count += deleted

                    if cursor == 0:
                        break

                self._logger.bind(tag=TAG).info(
                    f"Cache INVALIDATE: {search_pattern} (deleted {deleted_count} keys)"
                )
                return deleted_count

        except Exception as e:
            self._stats["errors"] += 1
            self._logger.bind(tag=TAG).error(
                f"Error invalidating pattern {search_pattern}: {e}"
            )
            return 0

    def get_stats(self) -> dict:
        """Get cache statistics"""
        return self._stats.copy()


# Global singleton instance
async_cache_manager = AsyncRedisCacheManager()
