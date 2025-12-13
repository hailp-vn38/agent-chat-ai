"""
VnExpress news source implementation - parse RSS feeds.

VnExpressSource:
- Lấy tin tức từ RSS feeds của VnExpress
- Topics được định nghĩa trong config file (.config.yml)
- Hỗ trợ extract nội dung chi tiết từ URLs

Methods:
- get_articles(topic, max_articles): Lấy danh sách bài viết RSS
- get_article_content(url): Extract nội dung từ URL bằng trafilatura

Ví dụ config:
    sources:
      vnexpress:
        name: "VnExpress"
        type: rss
        base_url: "https://vnexpress.net/rss"
        topics:
          - name: "Khoa học công nghệ"
            path: "/khoa-hoc-cong-nghe.rss"
"""

import feedparser
import httpx
import trafilatura
from datetime import datetime
from typing import Optional

from app.ai.plugins_func.functions.news.base import (
    NewsSource,
    SourceConfig,
    NewsArticle,
)
from app.core.logger import setup_logging

TAG = __name__
logger = setup_logging()


class VnExpressSource(NewsSource):
    """Lấy tin tức từ VnExpress RSS feeds."""

    def __init__(self, source_config: SourceConfig, timeout: int = 10):
        """
        Khởi tạo VnExpress source.

        Args:
            source_config: Cấu hình source từ config file
            timeout: Timeout cho HTTP requests (giây)
        """
        super().__init__(source_config)
        self.timeout = timeout
        self.session = None

    async def get_articles(
        self, topic: str, max_articles: int = 10
    ) -> list[NewsArticle]:
        """
        Lấy danh sách bài viết từ RSS feed.

        Args:
            topic: Tên topic
            max_articles: Số bài viết tối đa

        Returns:
            Danh sách NewsArticle
        """
        try:
            # Lấy path của topic từ config
            topic_path = self.get_topic_path(topic)
            if not topic_path:
                available = self.get_available_topics()
                logger.bind(tag=TAG).warning(
                    f"Topic '{topic}' không tìm thấy. "
                    f"Có sẵn: {', '.join(available)}"
                )
                return []

            # Xây dựng URL đầy đủ
            url = f"{self.config.base_url}{topic_path}"
            logger.bind(tag=TAG).debug(f"Fetch RSS từ: {url}")

            # Fetch RSS feed
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(url)
                response.raise_for_status()

            # Parse RSS feed
            feed = feedparser.parse(response.content)

            if feed.bozo and feed.bozo_exception:
                logger.bind(tag=TAG).warning(
                    f"RSS parse warning: {feed.bozo_exception}"
                )

            articles = []
            for entry in feed.entries[:max_articles]:
                try:
                    article = self._parse_entry(entry)
                    if article:
                        articles.append(article)
                except Exception as e:
                    logger.bind(tag=TAG).warning(f"Lỗi parse entry: {str(e)}")
                    continue

            logger.bind(tag=TAG).debug(
                f"Lấy được {len(articles)} bài viết từ '{topic}'"
            )
            return articles

        except httpx.HTTPError as e:
            logger.bind(tag=TAG).error(f"HTTP error: {str(e)}")
            return []
        except Exception as e:
            logger.bind(tag=TAG).error(f"Lỗi lấy articles: {str(e)}")
            return []

    async def get_article_content(self, url: str) -> Optional[str]:
        """
        Lấy nội dung chi tiết của bài viết.

        Args:
            url: URL của bài viết

        Returns:
            Nội dung dạng Markdown hoặc None nếu lỗi
        """
        try:
            logger.bind(tag=TAG).debug(f"Extract content từ: {url}")

            # Fetch URL
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(url)
                response.raise_for_status()

            # Extract content với trafilatura
            content = trafilatura.extract(
                response.text, include_comments=False, favor_precision=True
            )

            if not content:
                logger.bind(tag=TAG).warning(f"Không thể extract content từ {url}")
                return None

            # Convert to markdown (trafilatura returns markdown by default)
            logger.bind(tag=TAG).debug(f"Extract thành công từ {url}")
            return content

        except httpx.HTTPError as e:
            logger.bind(tag=TAG).error(f"HTTP error khi fetch {url}: {str(e)}")
            return None
        except Exception as e:
            logger.bind(tag=TAG).error(f"Lỗi extract content từ {url}: {str(e)}")
            return None

    def _parse_entry(self, entry) -> Optional[NewsArticle]:
        """
        Parse một RSS entry thành NewsArticle.

        Args:
            entry: feedparser entry object

        Returns:
            NewsArticle hoặc None nếu entry không hợp lệ
        """
        # Lấy title
        title = entry.get("title", "").strip()
        if not title:
            return None

        # Lấy link
        link = entry.get("link", "").strip()
        if not link:
            return None

        # Lấy ngày đăng
        pub_date = ""
        if "published" in entry:
            pub_date = entry.published
        elif "updated" in entry:
            pub_date = entry.updated

        # Lấy description
        description = ""
        if "summary" in entry:
            description = entry.summary.strip()
        elif "description" in entry:
            description = entry.description.strip()

        # Lấy image từ media:content hoặc media:thumbnail
        image_url = None
        if "media_content" in entry and len(entry.media_content) > 0:
            image_url = entry.media_content[0].get("url")
        elif "media_thumbnail" in entry and len(entry.media_thumbnail) > 0:
            image_url = entry.media_thumbnail[0].get("url")

        return NewsArticle(
            title=title,
            link=link,
            pub_date=pub_date,
            description=description,
            image_url=image_url,
            source=self.config.name,
        )
