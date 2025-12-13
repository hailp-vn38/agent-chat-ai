"""
News module - cung cấp công cụ đọc tin tức từ nhiều nguồn.

Tool functions:
- get_news_by_topic: Lấy danh sách tin tức theo chủ đề từ một nguồn tin
- get_news_detail: Lấy nội dung chi tiết của một bài viết từ URL

Ví dụ sử dụng:
    # Lấy danh sách tin công nghệ
    get_news_by_topic(source="vnexpress", topic="Khoa học công nghệ", conn=conn)

    # Lấy chi tiết bài viết
    get_news_detail(url="https://vnexpress.net/article", source="vnexpress", conn=conn)
"""

from app.ai.plugins_func.functions.news.base import (
    NewsSource,
    NewsArticle,
    TopicConfig,
    SourceConfig,
    NewsConfig,
    NewsListResponse,
)

# Import tool functions để đăng ký chúng
try:
    from app.ai.plugins_func.functions.news.get_news_list import (
        get_news_by_topic,
    )  # noqa: F401
    from app.ai.plugins_func.functions.news.get_news_detail import (
        get_news_detail,
    )  # noqa: F401
except ImportError as e:
    import warnings

    warnings.warn(f"Failed to import news tool functions: {e}")
    get_news_by_topic = None
    get_news_detail = None

__all__ = [
    "NewsSource",
    "NewsArticle",
    "TopicConfig",
    "SourceConfig",
    "NewsConfig",
    "NewsListResponse",
    "get_news_by_topic",
    "get_news_detail",
]
