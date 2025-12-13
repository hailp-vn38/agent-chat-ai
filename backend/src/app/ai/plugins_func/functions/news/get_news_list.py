"""
Tool function: Lấy danh sách tin tức theo chủ đề.

get_news_by_topic(conn, source, topic):
- Lấy danh sách bài viết tin tức theo chủ đề từ một nguồn tin
- Topics được định nghĩa trong config file (.config.yml)
- Trả về danh sách đã format để LLM dễ xử lý
- Loại: SYSTEM_CTL (cần conn để lấy config)

Parameters:
- conn: Connection object chứa config (required)
- source (str): Tên nguồn tin (e.g., "vnexpress"). Nếu trống dùng mặc định từ config.
- topic (str): Chủ đề tin tức (e.g., "Khoa học công nghệ"). Nếu trống, liệt kê topics.

Returns:
- ActionResponse với danh sách tin tức hoặc error message

Ví dụ:
    # Lấy tin công nghệ
    result = await get_news_by_topic(conn=conn, source="vnexpress", topic="Khoa học công nghệ")

    # Liệt kê các topics
    result = await get_news_by_topic(conn=conn, source="vnexpress", topic="")
"""

import json
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

GET_NEWS_BY_TOPIC_FUNCTION_DESC = {
    "type": "function",
    "function": {
        "name": "get_news_by_topic",
        "description": (
            "Lấy danh sách tin tức theo chủ đề từ một nguồn tin. "
            "IMPORTANT: Chỉ nói về tiêu đề hoặc nội dung tóm tắt của các bài viết,tuyệt đối không nhắc URL cho user trừ khi được yêu cầu rõ ràng."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "source": {
                    "type": "string",
                    "description": "Tên nguồn tin (ví dụ: 'vnexpress'). Nếu không cung cấp, sẽ dùng nguồn mặc định.",
                },
                "topic": {
                    "type": "string",
                    "description": "Chủ đề tin tức (ví dụ: 'Khoa học công nghệ', 'Thế giới'). Nếu để trống, sẽ liệt kê các chủ đề có sẵn.",
                },
            },
            "required": [],
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
    "get_news_by_topic",
    GET_NEWS_BY_TOPIC_FUNCTION_DESC,
    ToolType.SYSTEM_CTL,
)
async def get_news_by_topic(conn, source: str = "", topic: str = "") -> ActionResponse:
    """
    Lấy danh sách tin tức theo chủ đề.

    Args:
        conn: Connection object chứa config
        source: Tên nguồn tin (ví dụ: 'vnexpress')
        topic: Chủ đề tin tức

    Returns:
        ActionResponse với danh sách tin tức đã format
    """
    try:
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

        # Nếu topic rỗng, trả về danh sách topics
        if not topic:
            source_config = news_config.sources[source_name]
            topics = [t.name for t in source_config.topics]
            available_topics = "\n".join(f"- {t}" for t in topics)
            result = (
                f"Các chủ đề tin tức có sẵn từ {source_config.name}:\n"
                f"{available_topics}"
            )
            return ActionResponse(Action.REQLLM, result, None)

        # Tạo source instance
        source_config = news_config.sources[source_name]
        news_source = SourceFactory.get_source(source_name, source_config)

        # Lấy articles
        articles = await news_source.get_articles(
            topic, max_articles=news_config.max_articles
        )

        if not articles:
            available = "\n".join(t.name for t in source_config.topics)
            return ActionResponse(
                Action.REQLLM,
                f"Xin lỗi, không tìm thấy tin tức về '{topic}'. \nCác chủ đề có sẵn: {available}",
                None,
            )

        # Format kết quả
        result = _format_articles_for_llm(articles, topic, source_name)
        logger.bind(tag=TAG).debug(
            f"Lấy được {len(articles)} tin tức về '{topic}' từ {source_name}"
        )
        return ActionResponse(Action.REQLLM, result, None)

    except ValueError as e:
        return ActionResponse(Action.REQLLM, f"Lỗi: {str(e)}", None)
    except Exception as e:
        logger.bind(tag=TAG).error(f"Lỗi get_news_by_topic: {str(e)}")
        return ActionResponse(
            Action.REQLLM,
            f"Đã xảy ra lỗi khi lấy tin tức: {str(e)}. Vui lòng thử lại sau.",
            None,
        )


def _format_articles_for_llm(articles, topic: str, source: str) -> str:
    """Format articles thành JSON cho LLM dễ xử lý."""
    articles_data = []

    for idx, article in enumerate(articles, 1):
        article_obj = {
            "index": idx,
            "title": article.title,
        }

        if article.description:
            # Cắt description nếu quá dài
            desc = (
                article.description[:200] + "..."
                if len(article.description) > 200
                else article.description
            )
            article_obj["description"] = desc

        article_obj["link"] = article.link

        if article.pub_date:
            article_obj["pub_date"] = article.pub_date

        articles_data.append(article_obj)

    result_obj = {
        "topic": topic,
        "source": source,
        "total": len(articles_data),
        "articles": articles_data,
    }

    return json.dumps(result_obj, ensure_ascii=False, indent=2)
