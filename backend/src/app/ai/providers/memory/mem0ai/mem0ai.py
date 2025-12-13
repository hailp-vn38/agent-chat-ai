import traceback

from ..base import MemoryProviderBase, logger
from mem0 import MemoryClient
from app.ai.utils.util import check_model_key

TAG = __name__


class MemoryProvider(MemoryProviderBase):
    def __init__(self, config, summary_memory=None):
        super().__init__(config)
        self.api_key = config.get("api_key", "")
        model_key_msg = check_model_key("Mem0ai", self.api_key)
        if model_key_msg:
            logger.bind(tag=TAG).error(model_key_msg)
            self.use_mem0 = False
            return
        else:
            self.use_mem0 = True

        try:
            self.client = MemoryClient(api_key=self.api_key)
            logger.bind(tag=TAG).info("成功连接到 Mem0ai 服务")
        except Exception as e:
            logger.bind(tag=TAG).error(f"连接到 Mem0ai 服务时发生错误: {str(e)}")
            logger.bind(tag=TAG).error(f"详细错误: {traceback.format_exc()}")
            self.use_mem0 = False

    async def save_memory(self, msgs):
        if not self.use_mem0:
            return None
        if len(msgs) < 2:
            return None

        try:
            # Format the content as a message list for mem0
            # Mem0 API only accepts 'user' and 'assistant' roles
            # Map 'tool' role to 'assistant'
            messages = []
            for message in msgs:
                if message.role == "system":
                    continue
                if not message.content or not message.content.strip():
                    continue

                # Map tool role to assistant
                role = "assistant" if message.role == "tool" else message.role
                messages.append({"role": role, "content": message.content.strip()})

            # Skip if no valid messages after filtering
            if not messages or len(messages) == 0:
                logger.bind(tag=TAG).debug("Không có message hợp lệ để lưu")
                return None

            # Ensure user_id is a string
            user_id_str = str(self.role_id) if self.role_id else "unknown"

            # Log messages before sending for debugging
            logger.bind(tag=TAG).debug(f"Messages count: {len(messages)}")
            logger.bind(tag=TAG).debug(f"User ID: {user_id_str}")

            result = self.client.add(messages, user_id=user_id_str)
            logger.bind(tag=TAG).debug(f"Save memory result: {result}")
            return result
        except Exception as e:
            logger.bind(tag=TAG).error(f"保存记忆失败: {str(e)}")
            logger.bind(tag=TAG).error(f"详细错误: {traceback.format_exc()}")
            return None

    async def query_memory(self, query: str) -> str:
        if not self.use_mem0:
            return ""
        try:
            results = self.client.search(
                query=query, filters={"user_id": str(self.role_id)}
            )
            if not results or "results" not in results:
                return ""

            # Format each memory entry with its update time up to minutes
            memories = []
            for entry in results["results"]:
                timestamp = entry.get("updated_at", "")
                if timestamp:
                    try:
                        # Parse and reformat the timestamp
                        dt = timestamp.split(".")[0]  # Remove milliseconds
                        formatted_time = dt.replace("T", " ")
                    except:
                        formatted_time = timestamp
                memory = entry.get("memory", "")
                if timestamp and memory:
                    # Store tuple of (timestamp, formatted_string) for sorting
                    memories.append((timestamp, f"[{formatted_time}] {memory}"))

            # Sort by timestamp in descending order (newest first)
            memories.sort(key=lambda x: x[0], reverse=True)

            # Extract only the formatted strings
            memories_str = "\n".join(f"- {memory[1]}" for memory in memories)
            logger.bind(tag=TAG).debug(f"Query results: {memories_str}")
            return memories_str
        except Exception as e:
            logger.bind(tag=TAG).error(f"查询记忆失败: {str(e)}")
            return ""
