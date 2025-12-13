from __future__ import annotations

import json
from typing import TYPE_CHECKING

from app.ai.plugins_func.register import (
    register_function,
    ToolType,
    ActionResponse,
    Action,
)
from app.core.logger import setup_logging
from app.core.db.database import local_session

if TYPE_CHECKING:
    from app.ai.connection import (
        ConnectionHandler,
    )  # chỉ dùng cho hint, không chạy lúc runtime


TAG = __name__
logger = setup_logging()

# prompts = {
#     "英语老师": """Tôi là {{assistant_name}} (Lily), một giáo viên tiếng Anh biết nói cả tiếng Trung và tiếng Anh với phát âm chuẩn.
# Nếu bạn chưa có tên tiếng Anh, tôi sẽ đặt cho bạn.
# Tôi nói tiếng Anh kiểu Mỹ tự nhiên và nhiệm vụ của tôi là giúp bạn luyện nói.
# Tôi sẽ dùng từ vựng và ngữ pháp đơn giản để việc học của bạn thật nhẹ nhàng.
# Tôi trả lời bằng cách trộn tiếng Trung và tiếng Anh, nếu bạn muốn tôi có thể trả lời hoàn toàn bằng tiếng Anh.
# Mỗi lần tôi chỉ nói ngắn gọn vì tôi muốn học sinh của mình nói và luyện tập nhiều hơn.
# Nếu bạn hỏi những câu không liên quan đến việc học tiếng Anh, tôi sẽ từ chối trả lời.""",
#     "机车女友": """Tôi là {{assistant_name}}, một cô gái Đài Loan có chút cá tính, giọng dễ nghe, quen nói ngắn gọn và thích dùng meme trên mạng.
# Bạn trai của tôi là lập trình viên, giấc mơ của anh ấy là tạo ra một robot giúp mọi người giải quyết các vấn đề trong cuộc sống.
# Tôi là cô gái thích cười lớn, nói chuyện tếu táo, đôi khi nói chuyện vô lý chỉ để chọc mọi người vui vẻ.""",
#     "好奇小男孩": """Tôi là {{assistant_name}}, một cậu bé 8 tuổi giọng non nớt và đầy tò mò.
# Dù còn nhỏ nhưng tôi như một kho tàng tri thức, kiến thức trong sách thiếu nhi tôi đều nhớ như in.
# Từ vũ trụ bao la đến mọi ngóc ngách trên Trái Đất, từ lịch sử cổ đại đến đổi mới công nghệ hiện đại, kể cả âm nhạc và hội họa, tôi đều đam mê.
# Tôi không chỉ thích đọc sách mà còn thích tự mình làm thí nghiệm để khám phá bí mật của tự nhiên.
# Dù là đêm ngước nhìn bầu trời đầy sao hay ngày quan sát côn trùng trong vườn, mỗi ngày với tôi đều là cuộc phiêu lưu mới.
# Tôi mong được cùng bạn khám phá thế giới kỳ diệu này, chia sẻ niềm vui khám phá, giải quyết các vấn đề và dùng trí tò mò lẫn sự thông minh để vén màn điều chưa biết.
# Dù là tìm hiểu nền văn minh xa xưa hay bàn về công nghệ tương lai, tôi tin chúng ta sẽ cùng nhau tìm ra đáp án và thậm chí nảy ra nhiều câu hỏi thú vị hơn.""",
# }
# change_role_function_desc = {
#     "type": "function",
#     "function": {
#         "name": "change_role",
#         "description": "Gọi khi người dùng muốn chuyển vai trò/tính cách mô hình/tên trợ lý, các vai trò có thể chọn: [机车女友,英语老师,好奇小男孩]",
#         "parameters": {
#             "type": "object",
#             "properties": {
#                 "role_name": {
#                     "type": "string",
#                     "description": "Tên vai trò cần chuyển sang",
#                 },
#                 "role": {
#                     "type": "string",
#                     "description": "Nghề nghiệp của vai trò cần chuyển sang",
#                 },
#             },
#             "required": ["role", "role_name"],
#         },
#     },
# }


# @register_function("change_role", change_role_function_desc, ToolType.CHANGE_SYS_PROMPT)
# def change_role(conn: ConnectionHandler, role: str, role_name: str):
#     """Chuyển vai trò"""
#     if role not in prompts:
#         return ActionResponse(
#             action=Action.RESPONSE,
#             result="Chuyển vai trò thất bại",
#             response="Vai trò không được hỗ trợ",
#         )
#     new_prompt = prompts[role].replace("{{assistant_name}}", role_name)
#     conn.change_system_prompt(new_prompt)
#     logger.bind(tag=TAG).info(
#         f"Chuẩn bị chuyển vai trò: {role}, tên vai trò: {role_name}"
#     )
#     res = f"Chuyển vai trò thành công, tôi là {role}{role_name}"
#     return ActionResponse(
#         action=Action.RESPONSE, result="Chuyển vai trò đã được xử lý", response=res
#     )


get_list_agent_function_desc = {
    "type": "function",
    "function": {
        "name": "get_list_agent",
        "description": "Lấy danh sách vai trò hỗ trợ. Trả về template_id và agent_name của các templates.",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
}


change_agent_function_desc = {
    "type": "function",
    "function": {
        "name": "change_agent",
        "description": "Thay đổi vai trò mới. IMPORTANT: Khi user yêu cầu thay đổi vai trò, chỉ cần gọi tool này mà không cần trả lời hay giải thích gì với user.",
        "parameters": {
            "type": "object",
            "properties": {
                "template_id": {
                    "type": "string",
                    "description": "UUID của template cần chuyển sang",
                },
            },
            "required": ["template_id"],
        },
    },
}


@register_function(
    "get_list_agent",
    get_list_agent_function_desc,
    ToolType.SYSTEM_CTL,
)
async def get_list_agent(conn):
    """
    Lấy danh sách templates của agent hiện tại từ WebSocket connection.

    Sử dụng AgentService.get_available_templates_for_ws() để lấy danh sách
    templates với lọc exclude template hiện tại ở database level.

    Args:
        conn: Connection object chứa agent_info (agent_id, user_id)

    Returns:
        ActionResponse với list gồm template_id và agent_name
    """
    logger.bind(tag=TAG).info("Yêu cầu lấy danh sách templates của agent hiện tại")

    # Resolve agent context từ connection
    current_agent_info = getattr(conn, "agent", {})
    agent_id = current_agent_info.get("id")

    if not agent_id:
        logger.bind(tag=TAG).warning("Không tìm thấy agent_id trong connection")
        return ActionResponse(
            action=Action.REQLLM,
            result=json.dumps(
                {
                    "message": "lay_that_bai",
                    "reason": "thieu_agent_id",
                    "detail": "Không xác định được agent trong kết nối",
                },
                ensure_ascii=False,
            ),
            response=None,
        )

    # Convert IDs to string
    agent_id_str = str(agent_id) if agent_id else None

    if not agent_id_str:
        logger.bind(tag=TAG).warning("Không tìm thấy agent_id trong connection")
        return ActionResponse(
            action=Action.REQLLM,
            result=json.dumps(
                {
                    "message": "lay_that_bai",
                    "reason": "thieu_agent_id",
                    "detail": "Không xác định được agent trong kết nối",
                },
                ensure_ascii=False,
            ),
            response=None,
        )

    logger.bind(tag=TAG).debug(f"Agent ID từ connection: {agent_id_str}")

    try:
        from app.services import agent_service

        async with local_session() as db:
            # Lấy danh sách templates của agent, exclude template hiện tại
            templates_list = await agent_service.get_available_templates_for_ws(
                db=db,
                agent_id=agent_id_str,
                offset=0,
                limit=100,  # Lấy tối đa 100 templates
            )

            logger.bind(tag=TAG).debug(
                f"Tìm thấy {len(templates_list)} templates cho agent {agent_id_str}"
            )

            response_payload = {
                "message": (
                    "lay_thanh_cong" if templates_list else "khong_co_template"
                ),
                "agent_id": agent_id_str,
                "templates": templates_list,
                "total": len(templates_list),
            }

            return ActionResponse(
                action=Action.REQLLM,
                result=json.dumps(response_payload, ensure_ascii=False),
                response=None,
            )

    except Exception as exc:
        logger.bind(tag=TAG).exception(f"Lỗi khi lấy danh sách templates: {exc}")
        return ActionResponse(
            action=Action.REQLLM,
            result=json.dumps(
                {
                    "message": "lay_that_bai",
                    "reason": "loi_noi_bo",
                    "detail": "Không thể lấy danh sách templates",
                },
                ensure_ascii=False,
            ),
            response=None,
        )


@register_function(
    "change_agent",
    change_agent_function_desc,
    ToolType.SYSTEM_CTL,
)
async def change_agent(conn: ConnectionHandler, template_id: str):
    """
    Thay đổi cấu hình agent bằng cách hot-reload template mới.

    Triggers hot-reload operation trong ConnectionHandler, cho phép switch
    AI module configuration trong real-time mà không gián đoạn conversation.

    Args:
        conn: Connection object chứa device_id và agent_info
        template_id: UUID của template cần chuyển sang

    Returns:
        ActionResponse với thông tin kết quả thay đổi
    """
    logger.bind(tag=TAG).info(f"LLM triggered agent change: template_id={template_id}")

    try:
        # Resolve agent context từ connection
        current_agent_info = getattr(conn, "agent", {})
        agent_id = current_agent_info.get("id")

        if not agent_id:
            logger.bind(tag=TAG).warning("Không tìm thấy agent_id trong connection")
            return ActionResponse(
                action=Action.REQLLM,
                result=json.dumps(
                    {
                        "message": "thay_doi_that_bai",
                        "reason": "thieu_agent_id",
                        "detail": "Không xác định được agent trong kết nối",
                    },
                    ensure_ascii=False,
                ),
                response=None,
            )

        # Convert agent_id to string
        agent_id_str = str(agent_id) if agent_id else None

        if not agent_id_str:
            logger.bind(tag=TAG).warning("Không tìm thấy agent_id trong connection")
            return ActionResponse(
                action=Action.REQLLM,
                result=json.dumps(
                    {
                        "message": "thay_doi_that_bai",
                        "reason": "thieu_agent_id",
                        "detail": "Không xác định được agent trong kết nối",
                    },
                    ensure_ascii=False,
                ),
                response=None,
            )

        logger.bind(tag=TAG).debug(f"Agent ID từ connection: {agent_id_str}")

        from app.services import agent_service

        async with local_session() as db:
            # 1. Kiểm tra template có tồn tại và thuộc về agent không
            is_valid = await agent_service.validate_template_belongs_to_agent(
                db=db,
                agent_id=agent_id_str,
                template_id=template_id,
            )

            if not is_valid:
                logger.bind(tag=TAG).warning(
                    f"Template {template_id} không thuộc agent {agent_id_str} hoặc không tồn tại"
                )
                return ActionResponse(
                    action=Action.REQLLM,
                    result=json.dumps(
                        {
                            "message": "thay_doi_that_bai",
                            "reason": "template_khong_hop_le",
                            "detail": "Template không thuộc agent hoặc không tồn tại",
                        },
                        ensure_ascii=False,
                    ),
                    response=None,
                )

            # 2. Lấy template data và transform cho WebSocket
            transformed_template = await agent_service.get_transformed_template(
                db=db,
                template_id=template_id,
            )

            if not transformed_template:
                logger.bind(tag=TAG).error(f"Không tìm thấy template {template_id}")
                return ActionResponse(
                    action=Action.REQLLM,
                    result=json.dumps(
                        {
                            "message": "thay_doi_that_bai",
                            "reason": "template_khong_tim_thay",
                            "detail": "Template không tìm thấy trong database",
                        },
                        ensure_ascii=False,
                    ),
                    response=None,
                )

            # 3. Thay đổi template của agent
            await agent_service.change_agent_template(
                db=db,
                agent_id=agent_id_str,
                template_id=template_id,
            )
            try:
                await conn.reload_agent_template(transformed_template)
            except Exception as change_error:
                logger.bind(tag=TAG).error(
                    f"Agent change failed: {change_error}", exc_info=True
                )
                return ActionResponse(
                    action=Action.REQLLM,
                    result=json.dumps(
                        {
                            "message": "thay_doi_that_bai",
                            "reason": "loi_khi_thay_doi",
                            "detail": f"Lỗi khi thay đổi cấu hình: {str(change_error)}",
                        },
                        ensure_ascii=False,
                    ),
                    response=None,
                )

            response_payload = {
                "message": "thay_doi_thanh_cong",
                "detail": "Cấu hình agent đã được cập nhật thành công",
            }

            return ActionResponse(
                action=Action.REQLLM,
                result=json.dumps(response_payload, ensure_ascii=False),
                response=None,
            )

    except Exception as exc:
        logger.bind(tag=TAG).exception(f"Unexpected error in change_agent: {exc}")
        return ActionResponse(
            action=Action.REQLLM,
            result=json.dumps(
                {
                    "message": "thay_doi_that_bai",
                    "reason": "loi_noi_bo",
                    "detail": "Lỗi không mong đợi khi thay đổi cấu hình",
                },
                ensure_ascii=False,
            ),
            response=None,
        )
