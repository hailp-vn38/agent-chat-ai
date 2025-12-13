"""
Base classes and data models for news sources.

Classes:
- NewsSource: Abstract base class cho tất cả news sources
- NewsArticle: Đại diện cho một bài viết tin tức
- NewsConfig: Cấu hình toàn bộ news plugin từ file YAML
- SourceConfig: Cấu hình một nguồn tin
- TopicConfig: Cấu hình một topic/chủ đề tin tức

Để tạo một nguồn tin mới:
1. Extend class NewsSource
2. Implement async methods: get_articles() và get_article_content()
3. Đăng ký với SourceFactory.register_source()

Ví dụ:
    class MyNewsSource(NewsSource):
        async def get_articles(self, topic, max_articles=10):
            # Implementation
            pass

        async def get_article_content(self, url):
            # Implementation
            pass

    SourceFactory.register_source("my_source", MyNewsSource)
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class TopicConfig:
    """Cấu hình một topic tin tức."""

    name: str
    path: str


@dataclass
class SourceConfig:
    """Cấu hình một nguồn tin."""

    name: str
    type: str  # rss | api | scrape
    base_url: str
    topics: list[TopicConfig] = field(default_factory=list)


@dataclass
class NewsConfig:
    """Cấu hình toàn bộ news plugin."""

    default_source: str
    max_articles: int
    timeout: int
    max_content_length: int
    sources: dict[str, SourceConfig] = field(default_factory=dict)


@dataclass
class NewsArticle:
    """Một bài viết tin tức."""

    title: str
    link: str
    pub_date: str
    description: str
    image_url: Optional[str] = None
    source: str = ""


@dataclass
class NewsListResponse:
    """Phản hồi danh sách tin tức."""

    source: str
    topic: str
    articles: list[NewsArticle]
    fetched_at: str


class NewsSource(ABC):
    """Abstract base class cho tất cả các nguồn tin tức."""

    def __init__(self, source_config: SourceConfig):
        """
        Khởi tạo news source.

        Args:
            source_config: Cấu hình nguồn tin từ config file
        """
        self.config = source_config

    @abstractmethod
    async def get_articles(
        self, topic: str, max_articles: int = 10
    ) -> list[NewsArticle]:
        """
        Lấy danh sách bài viết theo topic.

        Args:
            topic: Tên topic (phải có trong config)
            max_articles: Số bài viết tối đa trả về

        Returns:
            Danh sách NewsArticle hoặc list rỗng nếu lỗi
        """
        pass

    @abstractmethod
    async def get_article_content(self, url: str) -> Optional[str]:
        """
        Lấy nội dung chi tiết của bài viết.

        Args:
            url: URL của bài viết

        Returns:
            Nội dung bài viết dạng Markdown hoặc None nếu lỗi
        """
        pass

    def get_available_topics(self) -> list[str]:
        """
        Lấy danh sách các topics có sẵn.

        Returns:
            Danh sách tên topics
        """
        return [topic.name for topic in self.config.topics]

    def get_topic_path(self, topic: str) -> Optional[str]:
        """
        Lấy path của một topic từ config.

        Args:
            topic: Tên topic

        Returns:
            Path của topic hoặc None nếu không tìm thấy
        """
        for t in self.config.topics:
            if t.name.lower() == topic.lower():
                return t.path
        return None
