"""
Knowledge Base Search Function - Cho phép LLM tìm kiếm trong cơ sở tri thức.

Sử dụng OpenMemory API để thực hiện semantic search trong knowledge base của agent.
"""

from app.ai.plugins_func.register import (
    Action,
    ActionResponse,
    ToolType,
    register_function,
)
from app.core.logger import setup_logging

TAG = __name__
logger = setup_logging()

SEARCH_KNOWLEDGE_BASE_FUNCTION_DESC = {
    "type": "function",
    "function": {
        "name": "search_knowledge_base",
        "description": (
            "Tìm kiếm thông tin trong cơ sở tri thức của agent. "
            "Sử dụng công cụ này khi cần tra cứu thông tin đã lưu trước đó như: "
            "tài liệu, ghi chú, kiến thức cá nhân, sự kiện, quy trình, hoặc bất kỳ thông tin nào "
            "mà người dùng đã thêm vào knowledge base. "
            "Ví dụ: 'tìm thông tin về dự án X', 'lịch họp tuần này', 'quy trình deploy'."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Câu hỏi hoặc từ khóa cần tìm kiếm trong cơ sở tri thức",
                },
                "k": {
                    "type": "integer",
                    "description": "Số lượng kết quả trả về (1-10), mặc định là 2",
                    "default": 2,
                },
                "sector": {
                    "type": "string",
                    "description": (
                        "Lọc theo loại tri thức (tùy chọn): "
                        "episodic (sự kiện, trải nghiệm), "
                        "semantic (kiến thức, sự thật), "
                        "procedural (quy trình, thói quen), "
                        "emotional (cảm xúc), "
                        "reflective (suy nghĩ, nhận định)"
                    ),
                    "enum": [
                        "episodic",
                        "semantic",
                        "procedural",
                        "emotional",
                        "reflective",
                    ],
                },
            },
            "required": ["query"],
        },
    },
}


@register_function(
    "search_knowledge_base",
    SEARCH_KNOWLEDGE_BASE_FUNCTION_DESC,
    ToolType.SYSTEM_CTL,
)
async def search_knowledge_base(
    conn=None,
    query: str = "",
    k: int = 2,
    sector: str | None = None,
    **kwargs,
) -> ActionResponse:
    """
    Tìm kiếm thông tin trong cơ sở tri thức của agent.

    Args:
        conn: Connection context (chứa agent_id)
        query: Câu hỏi hoặc từ khóa cần tìm
        k: Số lượng kết quả trả về (1-10)
        sector: Lọc theo sector (optional)

    Returns:
        ActionResponse với kết quả tìm kiếm
    """
    from app.services.openmemory import (
        OpenMemoryError,
        OpenMemoryUnavailableError,
        get_openmemory_service,
    )

    # Validate input
    if not query or not query.strip():
        return ActionResponse(
            action=Action.REQLLM,
            result="Vui lòng cung cấp từ khóa hoặc câu hỏi cần tìm kiếm.",
        )

    # Limit k to valid range
    k = max(1, min(k, 10))

    # Get agent_id from connection context
    agent_id = None
    if conn and hasattr(conn, "agent_id"):
        agent_id = conn.agent_id
    elif conn and hasattr(conn, "agent") and conn.agent:
        agent_id = (
            conn.agent.get("id")
            if isinstance(conn.agent, dict)
            else getattr(conn.agent, "id", None)
        )

    if not agent_id:
        logger.bind(tag=TAG).warning("No agent_id found in connection context")
        return ActionResponse(
            action=Action.REQLLM,
            result="Không thể xác định agent. Cơ sở tri thức không khả dụng.",
        )

    logger.bind(tag=TAG).info(
        f"Searching knowledge base for agent {agent_id}: query='{query[:50]}...', k={k}, sector={sector}"
    )

    try:
        service = get_openmemory_service()

        # Query OpenMemory với min_score=0.3 để lọc kết quả không liên quan
        # Cosine similarity: 0.0-0.3 (noise), 0.3-0.5 (có thể liên quan), 0.5+ (liên quan)
        response = await service.query_memory(
            agent_id=agent_id,
            query=query,
            k=k,
            min_score=0.5,
            sector=sector,
        )

        # Extract matches from response
        matches = response.get("matches", [])

        if not matches:
            return ActionResponse(
                action=Action.REQLLM,
                result="Không tìm thấy thông tin liên quan trong cơ sở tri thức.",
            )

        # Format results for LLM
        formatted_results = []
        for i, match in enumerate(matches, 1):
            content = match.get("content", "")
            primary_sector = match.get("primary_sector", "semantic")

            # Truncate long content
            if len(content) > 500:
                content = content[:500] + "..."

            # Format each result
            sector_info = f" [{primary_sector}]" if primary_sector else ""
            formatted_results.append(f"{i}. {content}{sector_info}")

        result_text = "\n\n".join(formatted_results)

        logger.bind(tag=TAG).info(
            f"Found {len(matches)} results for query '{query[:30]}...'"
        )

        return ActionResponse(
            action=Action.REQLLM,
            result=f"Kết quả tìm kiếm từ cơ sở tri thức ({len(matches)} kết quả):\n\n{result_text}",
        )

    except OpenMemoryUnavailableError as e:
        logger.bind(tag=TAG).error(f"OpenMemory service unavailable: {e}")
        return ActionResponse(
            action=Action.REQLLM,
            result="Dịch vụ cơ sở tri thức hiện không khả dụng. Vui lòng thử lại sau.",
        )

    except OpenMemoryError as e:
        logger.bind(tag=TAG).error(f"OpenMemory error: {e.message}")
        return ActionResponse(
            action=Action.REQLLM,
            result=f"Lỗi khi tìm kiếm cơ sở tri thức: {e.message}",
        )

    except Exception as e:
        logger.bind(tag=TAG).exception(
            f"Unexpected error in search_knowledge_base: {e}"
        )
        return ActionResponse(
            action=Action.REQLLM,
            result="Đã xảy ra lỗi khi tìm kiếm cơ sở tri thức.",
        )
