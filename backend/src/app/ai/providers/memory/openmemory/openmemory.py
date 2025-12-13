"""
OpenMemory Provider - Brain-Inspired Memory Storage

Integrates OpenMemory API for multi-sector memory management:
- Episodic: Event memories (temporal data)
- Semantic: Facts & preferences (factual data)
- Procedural: Habits, triggers (action patterns)
- Emotional: Sentiment states (tone analysis)
- Reflective: Meta memory & logs (audit trail)

Flow: Summarize dialogue → Extract JSON → Add to OpenMemory → Query on demand
"""

import json
import traceback
from typing import List, Dict, Optional, Any
from app.core.logger import setup_logging
from ..base import MemoryProviderBase

TAG = __name__
logger = setup_logging()

# Prompt để tóm tắt hội thoại thành JSON có sector
SUMMARIZATION_PROMPT = """Bạn là một chuyên gia tóm tắt hội thoại và phân loại thông tin. 
Tuân thủ các quy tắc sau:

1. Tóm tắt thông tin quan trọng của user để hỗ trợ cá nhân hóa tốt hơn trong các cuộc trò chuyện sau
2. Loại bỏ thông tin không liên quan trực tiếp đến user như: điều chỉnh âm lượng, phát nhạc, thời tiết, thoát, không muốn trò chuyện...
3. Không lưu kết quả điều khiển thiết bị (thành công hay thất bại) hoặc những lời nói vô nghĩa
4. Không tóm tắt nếu cuộc trò chuyện không có ý nghĩa
5. Xác định sector phù hợp nhất:
   - episodic: Sự kiện, trải nghiệm, khoảnh khắc có thời gian
   - semantic: Kiến thức, sự thật, ưa thích, thông tin tĩnh
   - procedural: Quuy trình, hướng dẫn, cách thực hiện
   - emotional: Cảm xúc, tâm trạng, phản ứng cảm tính
   - reflective: Phản ánh, suy ngẫm, meta-ý kiến về trò chuyện
6. Trả về JSON hợp lệ theo format sau, không có giải thích thêm:

```json
{
  "summary": "Tóm tắt nội dung (giới hạn 200 từ)",
  "tags": ["tag1", "tag2"],
  "sector": "semantic|episodic|procedural|emotional|reflective"
}
```

Nếu cuộc trò chuyện không có ý nghĩa, trả về:
```json
{
  "summary": "",
  "tags": [],
  "sector": "semantic"
}
```
"""


def extract_json_from_response(response: str) -> Optional[Dict[str, Any]]:
    """
    Trích xuất JSON từ response LLM.
    Hỗ trợ format ```json...``` hoặc raw JSON.
    """
    try:
        # Thử tìm JSON trong ```json...```
        start = response.find("```json")
        if start != -1:
            end = response.find("```", start + 7)
            if end != -1:
                json_str = response[start + 7 : end].strip()
                return json.loads(json_str)

        # Thử parse trực tiếp
        return json.loads(response)
    except (json.JSONDecodeError, ValueError) as e:
        logger.bind(tag=TAG).error(f"Không thể parse JSON từ LLM response: {e}")
        return None


class MemoryProvider(MemoryProviderBase):
    """OpenMemory provider - Tích hợp OpenMemory API cho multi-sector memory."""

    def __init__(self, config: Dict[str, Any], summary_memory=None):
        """
        Khởi tạo OpenMemory provider.

        Args:
            config: Configuration dict chứa:
                - mode: "local" hoặc "remote" (default: "remote")
                - Local mode:
                  - local_path: SQLite database path
                  - tier: "fast" | "balanced" | "quality"
                  - embeddings_provider: "synthetic" | "openai" | "gemini"
                  - embeddings_api_key: API key cho embeddings
                  - embeddings_model: Optional model name
                - Remote mode:
                  - base_url: OpenMemory API base URL
                  - api_key: Optional API key for authentication
                - Common:
                  - k: Số lượng memory results (default: 3)
                  - max_tokens: Max tokens cho LLM tóm tắt (default: 2000)
            summary_memory: Unused, for compatibility
        """
        super().__init__(config)

        self.mode = config.get("mode", "remote")
        self.k = config.get("k", 3)
        self.max_tokens = config.get("max_tokens", 2000)

        # Lazy load OpenMemory client
        self._client = None
        self._client_initialized = False
        self._initialization_error = None

        logger.bind(tag=TAG).info(
            f"OpenMemory provider initialized - mode: {self.mode}, k: {self.k}, max_tokens: {self.max_tokens}"
        )

    def _get_client(self):
        """Lazy initialize OpenMemory client (local or remote)."""
        if self._client_initialized:
            if self._initialization_error:
                raise Exception(self._initialization_error)
            return self._client

        try:
            # Dynamic import để tránh import error nếu không cài openmemory-py
            # Package name: openmemory-py (pip install), Import name: openmemory
            from openmemory import OpenMemory

            if self.mode == "local":
                # Local mode với embeddings config
                embeddings_config = self._build_embeddings_config()

                self._client = OpenMemory(
                    path=self.config.get("local_path", "./data/memory.sqlite"),
                    tier=self.config.get("tier", "fast"),
                    embeddings=embeddings_config,
                )
                logger.bind(tag=TAG).debug(
                    f"OpenMemory local client initialized: embeddings={embeddings_config.get('provider')}"
                )
            else:
                # Remote mode
                base_url = self.config.get("base_url", "http://localhost:8080").rstrip(
                    "/"
                )
                api_key = self.config.get("api_key", "")

                self._client = OpenMemory(
                    mode="remote",
                    url=base_url,
                    apiKey=api_key,
                )
                logger.bind(tag=TAG).debug(
                    f"OpenMemory remote client initialized: url={base_url}"
                )

            self._client_initialized = True
            return self._client

        except ImportError as e:
            error_msg = f"OpenMemory SDK (openmemory-py) not installed. Install with: pip install openmemory-py. Error: {e}"
            logger.bind(tag=TAG).error(error_msg)
            self._initialization_error = error_msg
            self._client_initialized = True
            raise ImportError(error_msg)
        except Exception as e:
            error_msg = f"Failed to initialize OpenMemory client: {e}"
            logger.bind(tag=TAG).error(error_msg)
            self._initialization_error = error_msg
            self._client_initialized = True
            raise

    def _build_embeddings_config(self) -> Dict[str, Any]:
        """
        Build embeddings config cho local mode.

        Returns:
            Dict with keys: provider, apiKey (optional), model (optional)
        """
        provider = self.config.get("embeddings_provider", "synthetic")

        if provider == "synthetic":
            return {"provider": "synthetic"}

        embeddings_config = {
            "provider": provider,
            "apiKey": self.config.get("embeddings_api_key", ""),
        }

        # Thêm model nếu có
        model = self.config.get("embeddings_model")
        if model:
            embeddings_config["model"] = model

        logger.bind(tag=TAG).debug(
            f"Built embeddings config: provider={provider}, has_key={bool(embeddings_config.get('apiKey'))}, model={model}"
        )

        return embeddings_config

    async def save_memory(self, msgs: List[Any]) -> Optional[Dict[str, Any]]:
        """
        Tóm tắt hội thoại và lưu vào OpenMemory.

        Flow:
        1. Convert Message list thành string
        2. Gọi LLM để tóm tắt theo JSON format
        3. Validate & extract JSON
        4. Add vào OpenMemory với user_id=role_id

        Args:
            msgs: List of Message objects from dialogue

        Returns:
            Dict with memory info or None if failed
        """
        try:
            # Kiểm tra LLM availability
            if self.llm is None:
                logger.bind(tag=TAG).error("LLM is not set for OpenMemory provider")
                return None

            # Kiểm tra min messages
            if len(msgs) < 2:
                logger.bind(tag=TAG).debug(
                    "Insufficient messages to summarize (need >= 2)"
                )
                return None

            # Convert Message list to string
            dialogue_str = self._format_dialogue(msgs)
            if not dialogue_str or dialogue_str.strip() == "":
                logger.bind(tag=TAG).debug("No valid dialogue content to summarize")
                return None

            # Call LLM to summarize
            logger.bind(tag=TAG).debug("Calling LLM for conversation summary")
            llm_response = self.llm.response_no_stream(
                system_prompt=SUMMARIZATION_PROMPT,
                user_prompt=dialogue_str,
                max_tokens=self.max_tokens,
                temperature=0.2,
            )

            # Extract and validate JSON
            summary_data = extract_json_from_response(llm_response)
            if not summary_data:
                logger.bind(tag=TAG).error("Failed to extract JSON from LLM response")
                return None

            # Skip if summary is empty
            if not summary_data.get("summary", "").strip():
                logger.bind(tag=TAG).debug("LLM returned empty summary, skipping save")
                return None

            # Add to OpenMemory
            result = await self._add_to_openmemory(summary_data)

            logger.bind(tag=TAG).info(
                f"Save memory successful - Role: {self.role_id}, Memory ID: {result.get('id') if result else 'N/A'}"
            )

            return result

        except Exception as e:
            logger.bind(tag=TAG).error(
                f"Error saving memory: {str(e)}\n{traceback.format_exc()}"
            )
            return None

    async def query_memory(self, query: str) -> str:
        """
        Query memories từ OpenMemory.

        Args:
            query: Search query string

        Returns:
            Formatted string of memory results để dùng cho LLM context
        """
        try:
            if not query or not query.strip():
                return ""

            client = self._get_client()

            # Query with user_id filter
            logger.bind(tag=TAG).debug(f"Querying OpenMemory for: {query} (k={self.k})")

            # Sử dụng run_in_executor để tránh asyncio.run() conflict
            import asyncio

            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                lambda: client.query(
                    query=query,
                    k=self.k,
                    filters={"user_id": str(self.role_id) if self.role_id else None},
                ),
            )

            # Format results to string
            formatted = self._format_query_results(result)

            logger.bind(tag=TAG).debug(f"Query returned {len(formatted)} characters")
            return formatted

        except Exception as e:
            logger.bind(tag=TAG).error(
                f"Error querying memory: {str(e)}\n{traceback.format_exc()}"
            )
            return ""

    def _format_dialogue(self, msgs: List[Any]) -> str:
        """
        Convert Message list to formatted dialogue string.

        Args:
            msgs: List of Message objects

        Returns:
            Formatted dialogue string
        """
        dialogue_parts = []

        for msg in msgs:
            role = getattr(msg, "role", "unknown")
            content = getattr(msg, "content", "")

            # Skip empty messages
            if not content or not str(content).strip():
                continue

            # Skip system messages
            if role == "system":
                continue

            # Format role
            role_label = {
                "user": "User",
                "assistant": "Assistant",
                "tool": "System",
            }.get(role, role.capitalize())

            dialogue_parts.append(f"{role_label}: {str(content).strip()}")

        return "\n".join(dialogue_parts)

    def _format_query_results(self, result: Dict[str, Any]) -> str:
        """
        Format OpenMemory query results to string.

        Args:
            result: Query result from OpenMemory API

        Returns:
            Formatted string for LLM context
        """
        if not result:
            return ""

        matches = result.get("matches", [])
        if not matches:
            return ""

        formatted_parts = ["[Previous Memories]"]

        for i, match in enumerate(matches, 1):
            content = match.get("content", "")
            sector = match.get("primary_sector", "unknown")
            score = match.get("score", 0)

            if not content:
                continue

            formatted_parts.append(
                f"{i}. [{sector.upper()}] (relevance: {score:.2f}) {content}"
            )

        return "\n".join(formatted_parts) if len(formatted_parts) > 1 else ""

    async def _add_to_openmemory(
        self, summary_data: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Add summarized memory to OpenMemory.

        Args:
            summary_data: Dict with keys: summary, tags, sector

        Returns:
            Response from OpenMemory API
        """
        try:
            client = self._get_client()

            summary = summary_data.get("summary", "").strip()
            tags = summary_data.get("tags", [])
            sector = summary_data.get("sector", "semantic")

            # Validate sector
            valid_sectors = [
                "episodic",
                "semantic",
                "procedural",
                "emotional",
                "reflective",
            ]
            if sector not in valid_sectors:
                logger.bind(tag=TAG).warning(
                    f"Invalid sector '{sector}', defaulting to 'semantic'"
                )
                sector = "semantic"

            # Add to OpenMemory
            logger.bind(tag=TAG).debug(
                f"Adding memory to OpenMemory - sector: {sector}, tags: {tags}"
            )

            # Sử dụng run_in_executor để tránh asyncio.run() conflict
            import asyncio

            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                lambda: client.add(
                    content=summary,
                    tags=tags if tags else [],
                    metadata={"sector": sector},
                    salience=0.7,  # Default salience
                    userId=str(self.role_id) if self.role_id else None,
                ),
            )

            logger.bind(tag=TAG).debug(f"Memory added successfully: {result}")
            return result

        except Exception as e:
            logger.bind(tag=TAG).error(
                f"Error adding memory to OpenMemory: {str(e)}\n{traceback.format_exc()}"
            )
            return None
