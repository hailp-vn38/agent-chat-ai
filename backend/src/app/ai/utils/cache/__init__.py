"""
Cache utilities for AI module
"""

from .async_redis_manager import AsyncRedisCacheManager, async_cache_manager
from .config import CacheConfig, CacheType

# Deprecated - kept for backward compatibility
from .manager import GlobalCacheManager, cache_manager

__all__ = [
    # New async Redis manager (recommended)
    "AsyncRedisCacheManager",
    "async_cache_manager",
    # Deprecated in-memory manager
    "GlobalCacheManager",
    "cache_manager",
    # Config
    "CacheType",
    "CacheConfig",
]
