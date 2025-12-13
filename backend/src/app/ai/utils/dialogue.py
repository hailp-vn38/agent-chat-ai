import uuid
import re
from typing import List, Dict
from datetime import datetime

from app.core.logger import get_logger

logger = get_logger(__name__)


class Message:
    def __init__(
        self,
        role: str,
        content: str = None,
        uniq_id: str = None,
        tool_calls=None,
        tool_call_id=None,
    ):
        self.uniq_id = uniq_id if uniq_id is not None else str(uuid.uuid4())
        self.role = role
        self.content = content
        self.tool_calls = tool_calls
        self.tool_call_id = tool_call_id

    @classmethod
    def create_tool_call(
        cls,
        function_id: str,
        function_name: str,
        function_arguments: str = "",
        uniq_id: str = None,
    ):
        """
        Tạo assistant message với tool_calls.

        Args:
            function_id: ID của function call
            function_name: Tên của function
            function_arguments: JSON string của arguments (mặc định là "{}")
            uniq_id: ID duy nhất cho message (tùy chọn)

        Returns:
            Message: Assistant message với tool_calls được cấu trúc sẵn
        """
        return cls(
            role="assistant",
            tool_calls=[
                {
                    "id": function_id,
                    "function": {
                        "arguments": (
                            "{}" if function_arguments == "" else function_arguments
                        ),
                        "name": function_name,
                    },
                    "type": "function",
                    "index": 0,
                }
            ],
            uniq_id=uniq_id,
        )

    @classmethod
    def create_tool_response(
        cls,
        tool_call_id: str,
        content: str,
        uniq_id: str = None,
    ):
        """
        Tạo tool message với tool_call_id để response.

        Args:
            tool_call_id: ID của tool call được response
            content: Nội dung response từ tool
            uniq_id: ID duy nhất cho message (tùy chọn)

        Returns:
            Message: Tool message với role="tool" và tool_call_id
        """
        return cls(
            role="tool",
            tool_call_id=(
                tool_call_id if tool_call_id is not None else str(uuid.uuid4())
            ),
            content=content,
            uniq_id=uniq_id,
        )


class Dialogue:
    def __init__(self):
        self.dialogue: List[Message] = []
        # Lấy thời gian hiện tại
        self.current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def put(self, message: Message):
        self.dialogue.append(message)

    def getMessages(self, m, dialogue):
        if m.tool_calls is not None:
            dialogue.append({"role": m.role, "tool_calls": m.tool_calls})
        elif m.role == "tool":
            dialogue.append(
                {
                    "role": m.role,
                    "tool_call_id": (
                        str(uuid.uuid4()) if m.tool_call_id is None else m.tool_call_id
                    ),
                    "content": m.content,
                }
            )
        else:
            dialogue.append({"role": m.role, "content": m.content})

    def get_llm_dialogue(self) -> List[Dict[str, str]]:
        # Gọi trực tiếp get_llm_dialogue_with_memory với None làm memory_str
        # Đảm bảo chức năng người nói hoạt động trên mọi luồng gọi
        return self.get_llm_dialogue_with_memory(None, None)

    def update_system_message(self, new_content: str):
        """Cập nhật hoặc thêm thông điệp hệ thống"""
        # Tìm thông điệp hệ thống đầu tiên
        system_msg = next((msg for msg in self.dialogue if msg.role == "system"), None)
        if system_msg:
            system_msg.content = new_content
        else:
            self.put(Message(role="system", content=new_content))

    def get_llm_dialogue_with_memory(
        self, memory_str: str = None, voiceprint_config: dict = None
    ) -> List[Dict[str, str]]:
        # Xây dựng đối thoại
        dialogue = []

        # Thêm prompt hệ thống và trí nhớ
        system_message = next(
            (msg for msg in self.dialogue if msg.role == "system"), None
        )

        if system_message:
            # Prompt hệ thống cơ bản
            enhanced_system_prompt = system_message.content

            # Thay thế placeholder thời gian
            enhanced_system_prompt = enhanced_system_prompt.replace(
                "{{current_time}}", datetime.now().strftime("%H:%M")
            )

            # Thêm mô tả cá nhân hóa người nói
            try:
                speakers = (
                    voiceprint_config.get("speakers", []) if voiceprint_config else []
                )
                if speakers:
                    enhanced_system_prompt += "\n\n<speakers_info>"
                    for speaker_str in speakers:
                        try:
                            parts = speaker_str.split(",", 2)
                            if len(parts) >= 2:
                                name = parts[1].strip()
                                # Nếu mô tả rỗng thì đặt thành ""
                                description = (
                                    parts[2].strip() if len(parts) >= 3 else ""
                                )
                                enhanced_system_prompt += f"\n- {name}: {description}"
                        except:
                            pass
                    enhanced_system_prompt += "\n\n</speakers_info>"
            except:
                # Bỏ qua lỗi nếu đọc cấu hình thất bại, tránh ảnh hưởng chức năng khác
                pass

            # Dùng regex để khớp thẻ <memory> bất kể nội dung bên trong
            if memory_str is not None:
                enhanced_system_prompt_before = enhanced_system_prompt
                enhanced_system_prompt = re.sub(
                    r"<memory>.*?</memory>",
                    f"<memory>\n{memory_str}\n</memory>",
                    enhanced_system_prompt,
                    flags=re.DOTALL,
                )

                if enhanced_system_prompt_before != enhanced_system_prompt:
                    # Cập nhật lại system_message.content để lưu memory vĩnh viễn
                    system_message.content = enhanced_system_prompt
                    logger.debug("Updated system message with new memory.")

            dialogue.append({"role": "system", "content": enhanced_system_prompt})

        # Thêm đoạn hội thoại của người dùng và trợ lý
        for m in self.dialogue:
            if m.role != "system":  # Bỏ qua thông điệp hệ thống gốc
                self.getMessages(m, dialogue)

        return dialogue
