"""
Trình quản lý bộ nhớ đệm toàn cục
"""

import time
import threading
from typing import Any, Optional, Dict
from collections import OrderedDict
from .strategies import CacheStrategy, CacheEntry
from .config import CacheConfig, CacheType


class GlobalCacheManager:
    """Trình quản lý bộ nhớ đệm toàn cục"""

    def __init__(self):
        self._logger = None
        self._caches: Dict[str, Dict[str, CacheEntry]] = {}
        self._configs: Dict[str, CacheConfig] = {}
        self._locks: Dict[str, threading.RLock] = {}
        self._global_lock = threading.RLock()
        self._last_cleanup = time.time()
        self._stats = {"hits": 0, "misses": 0, "evictions": 0, "cleanups": 0}

    @property
    def logger(self):
        """Khởi tạo logger trễ để tránh nhập vòng lặp"""
        if self._logger is None:
            from app.core.logger import setup_logging

            self._logger = setup_logging()
        return self._logger

    def _get_cache_name(self, cache_type: CacheType, namespace: str = "") -> str:
        """Tạo tên bộ nhớ đệm"""
        if namespace:
            return f"{cache_type.value}:{namespace}"
        return cache_type.value

    def _get_or_create_cache(self, cache_name: str, config: CacheConfig) -> Dict[str, CacheEntry]:
        """Lấy hoặc tạo vùng nhớ đệm"""
        with self._global_lock:
            if cache_name not in self._caches:
                self._caches[cache_name] = (
                    OrderedDict()
                    if config.strategy in [CacheStrategy.LRU, CacheStrategy.TTL_LRU]
                    else {}
                )
                self._configs[cache_name] = config
                self._locks[cache_name] = threading.RLock()
            return self._caches[cache_name]

    def set(
        self,
        cache_type: CacheType,
        key: str,
        value: Any,
        ttl: Optional[float] = None,
        namespace: str = "",
    ) -> None:
        """Ghi giá trị bộ nhớ đệm"""
        cache_name = self._get_cache_name(cache_type, namespace)
        config = self._configs.get(cache_name) or CacheConfig.for_type(cache_type)
        cache = self._get_or_create_cache(cache_name, config)

        # Dùng TTL trong cấu hình hoặc TTL được truyền vào
        effective_ttl = ttl if ttl is not None else config.ttl

        with self._locks[cache_name]:
            # Tạo mục bộ nhớ đệm
            entry = CacheEntry(value=value, timestamp=time.time(), ttl=effective_ttl)

            # Xử lý theo từng chiến lược
            if config.strategy in [CacheStrategy.LRU, CacheStrategy.TTL_LRU]:
                # Chiến lược LRU: nếu đã tồn tại thì di chuyển xuống cuối
                if key in cache:
                    del cache[key]
                cache[key] = entry

                # Kiểm tra giới hạn kích thước
                if config.max_size and len(cache) > config.max_size:
                    # Gỡ bỏ mục cũ nhất
                    oldest_key = next(iter(cache))
                    del cache[oldest_key]
                    self._stats["evictions"] += 1

            else:
                cache[key] = entry

                # Kiểm tra giới hạn kích thước
                if config.max_size and len(cache) > config.max_size:
                    # Chiến lược đơn giản: loại bỏ ngẫu nhiên một mục
                    victim_key = next(iter(cache))
                    del cache[victim_key]
                    self._stats["evictions"] += 1

        # Dọn dẹp mục hết hạn theo chu kỳ
        self._maybe_cleanup(cache_name)

    def get(self, cache_type: CacheType, key: str, namespace: str = "") -> Optional[Any]:
        """Lấy giá trị bộ nhớ đệm"""
        cache_name = self._get_cache_name(cache_type, namespace)

        if cache_name not in self._caches:
            self._stats["misses"] += 1
            return None

        cache = self._caches[cache_name]
        config = self._configs[cache_name]

        with self._locks[cache_name]:
            if key not in cache:
                self._stats["misses"] += 1
                return None

            entry = cache[key]

            # Kiểm tra hết hạn
            if entry.is_expired():
                del cache[key]
                self._stats["misses"] += 1
                return None

            # Cập nhật thông tin truy cập
            entry.touch()

            # Chiến lược LRU: di chuyển xuống cuối
            if config.strategy in [CacheStrategy.LRU, CacheStrategy.TTL_LRU]:
                del cache[key]
                cache[key] = entry

            self._stats["hits"] += 1
            return entry.value

    def delete(self, cache_type: CacheType, key: str, namespace: str = "") -> bool:
        """Xóa một mục khỏi bộ nhớ đệm"""
        cache_name = self._get_cache_name(cache_type, namespace)

        if cache_name not in self._caches:
            return False

        cache = self._caches[cache_name]

        with self._locks[cache_name]:
            if key in cache:
                del cache[key]
                return True
            return False

    def clear(self, cache_type: CacheType, namespace: str = "") -> None:
        """Xóa sạch bộ nhớ đệm được chỉ định"""
        cache_name = self._get_cache_name(cache_type, namespace)

        if cache_name not in self._caches:
            return

        with self._locks[cache_name]:
            self._caches[cache_name].clear()

    def invalidate_pattern(self, cache_type: CacheType, pattern: str, namespace: str = "") -> int:
        """Vô hiệu các mục bộ nhớ đệm theo mẫu"""
        cache_name = self._get_cache_name(cache_type, namespace)

        if cache_name not in self._caches:
            return 0

        cache = self._caches[cache_name]
        deleted_count = 0

        with self._locks[cache_name]:
            keys_to_delete = [key for key in cache.keys() if pattern in key]
            for key in keys_to_delete:
                del cache[key]
                deleted_count += 1

        return deleted_count

    def _cleanup_expired(self, cache_name: str) -> int:
        """Dọn dẹp các mục đã hết hạn"""
        if cache_name not in self._caches:
            return 0

        cache = self._caches[cache_name]
        deleted_count = 0

        with self._locks[cache_name]:
            expired_keys = [key for key, entry in cache.items() if entry.is_expired()]
            for key in expired_keys:
                del cache[key]
                deleted_count += 1

        return deleted_count

    def _maybe_cleanup(self, cache_name: str):
        """Kiểm tra dọn dẹp định kỳ"""
        config = self._configs.get(cache_name)
        if not config:
            return

        now = time.time()
        if now - self._last_cleanup > config.cleanup_interval:
            self._last_cleanup = now
            deleted = self._cleanup_expired(cache_name)
            if deleted > 0:
                self._stats["cleanups"] += 1
                self.logger.debug(f"Dọn dẹp bộ nhớ đệm {cache_name}: đã xóa {deleted} mục hết hạn")


# Tạo một thể hiện trình quản lý bộ nhớ đệm toàn cục
cache_manager = GlobalCacheManager()
