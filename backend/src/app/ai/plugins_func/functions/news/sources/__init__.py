"""
News source factory and utilities.

SourceFactory:
- get_source(source_name, source_config): Tạo instance của một news source
- register_source(name, source_class): Đăng ký một news source mới
- get_available_sources(): Lấy danh sách sources có sẵn

Các sources hiện có:
- vnexpress: Lấy tin từ VnExpress RSS feeds

Ví dụ:
    config = SourceConfig(...)
    source = SourceFactory.get_source("vnexpress", config)
    articles = await source.get_articles("Khoa học công nghệ")
"""

from app.ai.plugins_func.functions.news.base import SourceConfig, NewsSource
from app.core.logger import setup_logging

TAG = __name__
logger = setup_logging()


class SourceFactory:
    """Factory để tạo news source instances."""

    # Mapping giữa source name và class
    _sources = {}

    @classmethod
    def _load_sources(cls):
        """Lazy load các sources để tránh circular imports."""
        if not cls._sources:
            from app.ai.plugins_func.functions.news.sources.vnexpress import (
                VnExpressSource,
            )

            cls._sources["vnexpress"] = VnExpressSource

    @classmethod
    def get_source(cls, source_name: str, source_config: SourceConfig) -> NewsSource:
        """
        Tạo instance của news source.

        Args:
            source_name: Tên source (e.g., "vnexpress")
            source_config: Cấu hình source

        Returns:
            Instance của NewsSource

        Raises:
            ValueError: Nếu source không được hỗ trợ
        """
        cls._load_sources()
        source_class = cls._sources.get(source_name)
        if not source_class:
            raise ValueError(
                f"Source '{source_name}' không được hỗ trợ. "
                f"Có sẵn: {', '.join(cls._sources.keys())}"
            )
        logger.bind(tag=TAG).debug(f"Tạo source instance: {source_name}")
        return source_class(source_config)

    @classmethod
    def register_source(cls, name: str, source_class: type[NewsSource]):
        """
        Đăng ký một news source mới.

        Args:
            name: Tên source
            source_class: Class của source (phải extend NewsSource)
        """
        cls._sources[name] = source_class
        logger.bind(tag=TAG).info(f"Đã đăng ký source: {name}")

    @classmethod
    def get_available_sources(cls) -> list[str]:
        """Lấy danh sách các sources có sẵn."""
        cls._load_sources()
        return list(cls._sources.keys())
