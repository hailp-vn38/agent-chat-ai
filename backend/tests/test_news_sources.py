"""
Unit tests for news sources.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import feedparser

from app.ai.plugins_func.functions.news.base import (
    NewsSource,
    NewsArticle,
    TopicConfig,
    SourceConfig,
)
from app.ai.plugins_func.functions.news.sources.vnexpress import VnExpressSource
from app.ai.plugins_func.functions.news.sources import SourceFactory


class TestVnExpressSource:
    """Tests for VnExpressSource."""

    @pytest.fixture
    def source_config(self):
        """Create a sample source config."""
        topics = [
            TopicConfig(name="Khoa học công nghệ", path="/khoa-hoc-cong-nghe.rss"),
            TopicConfig(name="Thể thao", path="/the-thao.rss"),
        ]
        return SourceConfig(
            name="VnExpress",
            type="rss",
            base_url="https://vnexpress.net/rss",
            topics=topics,
        )

    @pytest.fixture
    def source(self, source_config):
        """Create a VnExpressSource instance."""
        return VnExpressSource(source_config, timeout=5)

    @pytest.mark.asyncio
    async def test_get_articles_success(self, source):
        """Test successful article fetching."""
        mock_rss_content = """<?xml version="1.0" encoding="UTF-8"?>
        <rss version="2.0">
            <channel>
                <title>VnExpress</title>
                <item>
                    <title>Tin test 1</title>
                    <link>https://vnexpress.net/article1</link>
                    <pubDate>Mon, 01 Jan 2024 10:00:00 +0000</pubDate>
                    <description>Mô tả tin test 1</description>
                </item>
                <item>
                    <title>Tin test 2</title>
                    <link>https://vnexpress.net/article2</link>
                    <pubDate>Mon, 01 Jan 2024 09:00:00 +0000</pubDate>
                    <description>Mô tả tin test 2</description>
                </item>
            </channel>
        </rss>"""

        with patch("httpx.AsyncClient") as mock_client:
            mock_response = AsyncMock()
            mock_response.content = mock_rss_content.encode()
            mock_response.raise_for_status = AsyncMock()

            mock_client.return_value.__aenter__.return_value.get.return_value = (
                mock_response
            )

            articles = await source.get_articles("Khoa học công nghệ", max_articles=10)

            assert len(articles) == 2
            assert articles[0].title == "Tin test 1"
            assert articles[0].link == "https://vnexpress.net/article1"
            assert articles[0].description == "Mô tả tin test 1"
            assert articles[0].source == "VnExpress"

    @pytest.mark.asyncio
    async def test_get_articles_invalid_topic(self, source):
        """Test fetching with invalid topic."""
        articles = await source.get_articles("Invalid Topic", max_articles=10)
        assert articles == []

    @pytest.mark.asyncio
    async def test_get_articles_network_error(self, source):
        """Test handling network errors."""
        import httpx

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get.side_effect = (
                httpx.HTTPError("Network error")
            )

            articles = await source.get_articles("Khoa học công nghệ")
            assert articles == []

    @pytest.mark.asyncio
    async def test_get_article_content_success(self, source):
        """Test successful content extraction."""
        mock_html = "<html><body><article><h1>Test Title</h1><p>Test content</p></article></body></html>"

        with patch("httpx.AsyncClient") as mock_client, patch(
            "trafilatura.extract"
        ) as mock_extract:
            mock_response = AsyncMock()
            mock_response.text = mock_html
            mock_response.raise_for_status = AsyncMock()

            mock_client.return_value.__aenter__.return_value.get.return_value = (
                mock_response
            )
            mock_extract.return_value = "# Test Title\n\nTest content"

            content = await source.get_article_content("https://vnexpress.net/article1")

            assert content == "# Test Title\n\nTest content"
            mock_extract.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_article_content_extraction_failure(self, source):
        """Test handling extraction failure."""
        with patch("httpx.AsyncClient") as mock_client, patch(
            "trafilatura.extract"
        ) as mock_extract:
            mock_response = AsyncMock()
            mock_response.text = "<html></html>"
            mock_response.raise_for_status = AsyncMock()

            mock_client.return_value.__aenter__.return_value.get.return_value = (
                mock_response
            )
            mock_extract.return_value = None

            content = await source.get_article_content("https://vnexpress.net/article1")

            assert content is None

    def test_get_available_topics(self, source):
        """Test getting available topics."""
        topics = source.get_available_topics()
        assert len(topics) == 2
        assert "Khoa học công nghệ" in topics
        assert "Thể thao" in topics

    def test_get_topic_path_found(self, source):
        """Test getting topic path when found."""
        path = source.get_topic_path("Khoa học công nghệ")
        assert path == "/khoa-hoc-cong-nghe.rss"

    def test_get_topic_path_not_found(self, source):
        """Test getting topic path when not found."""
        path = source.get_topic_path("Invalid")
        assert path is None

    def test_get_topic_path_case_insensitive(self, source):
        """Test that topic lookup is case-insensitive."""
        path = source.get_topic_path("KHOA HỌC CÔNG NGHỆ")
        assert path == "/khoa-hoc-cong-nghe.rss"


class TestSourceFactory:
    """Tests for SourceFactory."""

    def test_get_source_vnexpress(self):
        """Test getting VnExpress source."""
        topics = [TopicConfig(name="Test", path="/test.rss")]
        config = SourceConfig(
            name="VnExpress",
            type="rss",
            base_url="https://vnexpress.net/rss",
            topics=topics,
        )

        source = SourceFactory.get_source("vnexpress", config)
        assert isinstance(source, VnExpressSource)
        assert source.config.name == "VnExpress"

    def test_get_source_invalid(self):
        """Test getting invalid source."""
        topics = [TopicConfig(name="Test", path="/test.rss")]
        config = SourceConfig(
            name="Test", type="rss", base_url="https://test.com", topics=topics
        )

        with pytest.raises(ValueError) as excinfo:
            SourceFactory.get_source("invalid_source", config)
        assert "không được hỗ trợ" in str(excinfo.value)

    def test_get_available_sources(self):
        """Test getting available sources."""
        sources = SourceFactory.get_available_sources()
        assert "vnexpress" in sources
