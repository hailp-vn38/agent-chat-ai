"""
Tool function: Lấy chi tiết nội dung bài viết tin tức.

get_news_detail(conn, url, source):
- Extract nội dung chi tiết của một bài viết từ URL
- Sử dụng trafilatura để extract main content
- Hỗ trợ nhiều nguồn tin (RSS, web scraping, etc.)
- Trả về nội dung dạng Markdown
- Loại: SYSTEM_CTL (cần conn để lấy config)

Parameters:
- conn: Connection object chứa config (required)
- url (str): URL của bài viết. Phải bắt đầu với "http://" hoặc "https://"
- source (str): Tên nguồn tin (e.g., "vnexpress"). Nếu trống dùng mặc định từ config.

Returns:
- ActionResponse với nội dung bài viết hoặc error message

Ví dụ:
    result = await get_news_detail(
        conn=conn,
        url="https://vnexpress.net/article-xyz",
        source="vnexpress"
    )
"""

from app.ai.plugins_func.register import (
    register_function,
    ToolType,
    ActionResponse,
    Action,
)
from app.ai.plugins_func.functions.news.base import (
    NewsConfig,
    SourceConfig,
    TopicConfig,
)
from app.ai.plugins_func.functions.news.sources import SourceFactory
from app.core.logger import setup_logging

TAG = __name__
logger = setup_logging()

GET_NEWS_DETAIL_FUNCTION_DESC = {
    "type": "function",
    "function": {
        "name": "get_news_detail",
        "description": (
            "Lấy nội dung chi tiết của một bài viết tin tức từ URL. "
            "Hệ thống sẽ tự động extract nội dung chính từ bài viết, "
            "loại bỏ các phần không liên quan, và convert sang định dạng dễ đọc. "
            "Trả về toàn bộ nội dung bài viết dưới dạng Markdown."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "URL của bài viết (ví dụ: 'https://vnexpress.net/...')",
                },
                "source": {
                    "type": "string",
                    "description": "Tên nguồn tin (ví dụ: 'vnexpress'). Nếu không cung cấp, sẽ dùng nguồn mặc định.",
                },
            },
            "required": ["url"],
        },
    },
}


def _load_news_config(conn) -> NewsConfig | None:
    """
    Load cấu hình news từ conn.config.

    Returns:
        NewsConfig hoặc None nếu không có config
    """
    try:
        if not hasattr(conn, "config"):
            logger.bind(tag=TAG).error("conn không có config")
            return None

        news_config_dict = conn.config.get("plugins", {}).get("news")
        if not news_config_dict:
            logger.bind(tag=TAG).error("Không tìm thấy config plugins.news")
            return None

        # Parse source configs
        sources = {}
        for source_name, source_dict in news_config_dict.get("sources", {}).items():
            topics = [
                TopicConfig(name=t["name"], path=t["path"])
                for t in source_dict.get("topics", [])
            ]
            sources[source_name] = SourceConfig(
                name=source_dict.get("name", source_name),
                type=source_dict.get("type", "rss"),
                base_url=source_dict.get("base_url", ""),
                topics=topics,
            )

        return NewsConfig(
            default_source=news_config_dict.get("default_source", "vnexpress"),
            max_articles=news_config_dict.get("max_articles", 10),
            timeout=news_config_dict.get("timeout", 10),
            max_content_length=news_config_dict.get("max_content_length", 4000),
            sources=sources,
        )
    except Exception as e:
        logger.bind(tag=TAG).error(f"Lỗi load news config: {str(e)}")
        return None


@register_function(
    "get_news_detail",
    GET_NEWS_DETAIL_FUNCTION_DESC,
    ToolType.SYSTEM_CTL,
)
async def get_news_detail(conn, url: str, source: str = "") -> ActionResponse:
    """
    Lấy nội dung chi tiết của bài viết tin tức.

    Args:
        conn: Connection object chứa config
        url: URL của bài viết
        source: Tên nguồn tin (tùy chọn)

    Returns:
        ActionResponse với nội dung bài viết đã extract
    """
    try:
        # Validate URL
        if not url or not isinstance(url, str):
            return ActionResponse(
                Action.REQLLM,
                "URL không hợp lệ. Vui lòng cung cấp URL đầy đủ của bài viết.",
                None,
            )

        if not url.startswith("http"):
            return ActionResponse(
                Action.REQLLM,
                "URL phải bắt đầu với 'http://' hoặc 'https://'. Vui lòng kiểm tra lại URL.",
                None,
            )

        # Load config
        news_config = _load_news_config(conn)
        if not news_config:
            return ActionResponse(
                Action.REQLLM,
                "Không thể load cấu hình tin tức. Vui lòng kiểm tra lại hoặc thử lại sau.",
                None,
            )

        # Xác định source
        source_name = source or news_config.default_source
        if source_name not in news_config.sources:
            available = ", ".join(news_config.sources.keys())
            return ActionResponse(
                Action.REQLLM,
                f"Nguồn tin '{source_name}' không được hỗ trợ. Các nguồn có sẵn: {available}",
                None,
            )

        # Tạo source instance
        source_config = news_config.sources[source_name]
        news_source = SourceFactory.get_source(source_name, source_config)

        # Extract content
        content = await news_source.get_article_content(url)

        if not content:
            return ActionResponse(
                Action.REQLLM,
                f"Xin lỗi, không thể lấy nội dung từ bài viết. URL có thể không hợp lệ hoặc bài viết không tồn tại. Vui lòng thử với URL khác.",
                None,
            )

        # Truncate nếu quá dài
        max_length = news_config.max_content_length
        if len(content) > max_length:
            content = (
                content[:max_length]
                + "\n\n[Nội dung đã được rút gọn. "
                + f"Để đọc đầy đủ, vui lòng truy cập: {url}]"
            )

        logger.bind(tag=TAG).debug(f"Extract content từ {url} thành công")
        return ActionResponse(Action.REQLLM, content, None)

    except Exception as e:
        logger.bind(tag=TAG).error(f"Lỗi get_news_detail: {str(e)}")
        return ActionResponse(
            Action.REQLLM,
            f"Đã xảy ra lỗi khi lấy nội dung bài viết: {str(e)}. Vui lòng thử lại sau.",
            None,
        )
