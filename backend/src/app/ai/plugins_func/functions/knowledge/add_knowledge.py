"""
Add Knowledge Function - Cho phép LLM thêm thông tin vào cơ sở tri thức.

Sử dụng OpenMemory API để lưu trữ tri thức mới vào knowledge base của agent.
LLM có thể sử dụng tool này khi người dùng yêu cầu lưu/ghi nhớ thông tin.
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

ADD_KNOWLEDGE_FUNCTION_DESC = {
    "type": "function",
    "function": {
        "name": "add_knowledge",
        "description": (
            "Thêm thông tin mới vào cơ sở tri thức của agent. "
            "Sử dụng công cụ này khi người dùng yêu cầu ghi nhớ, lưu trữ hoặc thêm thông tin mới. "
            "Ví dụ: 'ghi nhớ số điện thoại này', 'lưu lại thông tin cuộc họp', "
            "'thêm vào ghi chú rằng...', 'nhớ rằng tôi thích cà phê đen'."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "content": {
                    "type": "string",
                    "description": "Nội dung cần lưu vào cơ sở tri thức. Cần viết rõ ràng, đầy đủ ngữ cảnh.",
                },
                "sector": {
                    "type": "string",
                    "description": (
                        "Loại tri thức để phân loại (tùy chọn): "
                        "episodic (sự kiện, trải nghiệm cá nhân), "
                        "semantic (kiến thức, sự thật, thông tin tham khảo), "
                        "procedural (quy trình, cách làm, thói quen), "
                        "emotional (cảm xúc, sở thích, mong muốn), "
                        "reflective (suy nghĩ, nhận định, đánh giá)"
                    ),
                    "enum": [
                        "episodic",
                        "semantic",
                        "procedural",
                        "emotional",
                        "reflective",
                    ],
                    "default": "semantic",
                },
                "tags": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Các thẻ tag để dễ dàng tìm kiếm sau này (tùy chọn)",
                },
                "salience": {
                    "type": "number",
                    "description": "Mức độ quan trọng từ 0.0 đến 1.0 (mặc định 0.5)",
                    "minimum": 0.0,
                    "maximum": 1.0,
                    "default": 0.5,
                },
            },
            "required": ["content"],
        },
    },
}


@register_function(
    "add_knowledge",
    ADD_KNOWLEDGE_FUNCTION_DESC,
    ToolType.SYSTEM_CTL,
)
async def add_knowledge(
    conn=None,
    content: str = "",
    sector: str = "semantic",
    tags: list[str] | None = None,
    salience: float = 0.5,
    **kwargs,
) -> ActionResponse:
    """
    Thêm thông tin mới vào cơ sở tri thức của agent.

    Args:
        conn: Connection context (chứa agent_id)
        content: Nội dung cần lưu
        sector: Loại tri thức (episodic, semantic, procedural, emotional, reflective)
        tags: Danh sách tags để phân loại
        salience: Mức độ quan trọng (0.0 - 1.0)

    Returns:
        ActionResponse với kết quả thêm tri thức
    """
    from app.services.openmemory import (
        OpenMemoryError,
        OpenMemoryUnavailableError,
        get_openmemory_service,
    )

    # Validate input
    if not content or not content.strip():
        return ActionResponse(
            action=Action.REQLLM,
            result="Vui lòng cung cấp nội dung cần lưu vào cơ sở tri thức.",
        )

    # Validate sector
    valid_sectors = ["episodic", "semantic", "procedural", "emotional", "reflective"]
    if sector not in valid_sectors:
        sector = "semantic"

    # Validate salience
    salience = max(0.0, min(1.0, salience))

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
            result="Không thể xác định agent. Không thể lưu vào cơ sở tri thức.",
        )

    logger.bind(tag=TAG).info(
        f"Adding knowledge for agent {agent_id}: content='{content[:50]}...', sector={sector}"
    )

    try:
        service = get_openmemory_service()

        # Add memory to OpenMemory
        result = await service.add_memory(
            agent_id=agent_id,
            content=content.strip(),
            sector=sector,
            tags=tags or [],
            salience=salience,
        )

        memory_id = result.get("id", "")
        assigned_sector = result.get("primary_sector", sector)

        logger.bind(tag=TAG).info(
            f"Successfully added knowledge {memory_id} to sector {assigned_sector}"
        )

        # Format response for LLM
        sector_names = {
            "episodic": "sự kiện",
            "semantic": "kiến thức",
            "procedural": "quy trình",
            "emotional": "cảm xúc",
            "reflective": "suy nghĩ",
        }
        sector_display = sector_names.get(assigned_sector, assigned_sector)

        tags_info = f" với tags: {', '.join(tags)}" if tags else ""

        return ActionResponse(
            action=Action.REQLLM,
            result=f"Đã lưu thông tin vào cơ sở tri thức (loại: {sector_display}){tags_info}.",
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
            result=f"Lỗi khi lưu vào cơ sở tri thức: {e.message}",
        )

    except Exception as e:
        logger.bind(tag=TAG).exception(f"Unexpected error in add_knowledge: {e}")
        return ActionResponse(
            action=Action.REQLLM,
            result="Đã xảy ra lỗi khi lưu thông tin vào cơ sở tri thức.",
        )
