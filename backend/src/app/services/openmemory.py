"""
OpenMemory Service - HTTP client wrapper for OpenMemory API.

Brain-Inspired Memory System with features:
- Multi-sector memory classification (episodic, semantic, procedural, emotional, reflective)
- Exponential decay with sector-specific rates
- Vector similarity search with cosine distance
- Memory reinforcement and salience tracking
- User memory management and summaries

All operations use agent_id as user_id for isolation.
"""

from typing import Any

import httpx

from ..core.config import settings
from ..core.logger import get_logger

logger = get_logger(__name__)


# Brain sector constants
SECTORS = {
    "EPISODIC": "episodic",  # Event memories (temporal data)
    "SEMANTIC": "semantic",  # Facts & preferences (factual data)
    "PROCEDURAL": "procedural",  # Habits, triggers (action patterns)
    "EMOTIONAL": "emotional",  # Sentiment states (tone analysis)
    "REFLECTIVE": "reflective",  # Meta memory & logs (audit trail)
}


class OpenMemoryError(Exception):
    """Base exception for OpenMemory service errors."""

    def __init__(self, message: str, status_code: int | None = None):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


class OpenMemoryUnavailableError(OpenMemoryError):
    """OpenMemory service is unavailable."""

    pass


class OpenMemoryNotFoundError(OpenMemoryError):
    """Memory item not found."""

    pass


class OpenMemoryService:
    """
    HTTP client wrapper for OpenMemory API.

    Supports five memory sectors:
    - Episodic: Event memories (temporal data)
    - Semantic: Facts & preferences (factual data)
    - Procedural: Habits, triggers (action patterns)
    - Emotional: Sentiment states (tone analysis)
    - Reflective: Meta memory & logs (audit trail)
    """

    def __init__(
        self,
        base_url: str,
        api_key: str,
        timeout: int = 30,
    ):
        """
        Initialize OpenMemory service.

        Args:
            base_url: OpenMemory server URL
            api_key: API key for authentication
            timeout: Request timeout in seconds
        """
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create async HTTP client."""
        if self._client is None or self._client.is_closed:
            headers = {"Content-Type": "application/json"}
            if self.api_key:
                headers["x-api-key"] = self.api_key

            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers=headers,
                timeout=httpx.Timeout(self.timeout),
            )
        return self._client

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    async def _request(
        self,
        method: str,
        path: str,
        json: dict | None = None,
        params: dict | None = None,
    ) -> dict:
        """
        Make HTTP request to OpenMemory API.

        Args:
            method: HTTP method (GET, POST, PATCH, DELETE)
            path: API path
            json: Request body
            params: Query parameters

        Returns:
            Response JSON

        Raises:
            OpenMemoryUnavailableError: Service unavailable
            OpenMemoryNotFoundError: Resource not found
            OpenMemoryError: Other errors
        """
        client = await self._get_client()

        try:
            response = await client.request(
                method=method,
                url=path,
                json=json,
                params=params,
            )

            if response.status_code == 404:
                raise OpenMemoryNotFoundError(
                    f"Resource not found: {path}",
                    status_code=404,
                )

            if response.status_code >= 500:
                raise OpenMemoryUnavailableError(
                    f"OpenMemory server error: {response.status_code}",
                    status_code=response.status_code,
                )

            if response.status_code >= 400:
                error_detail = response.text
                raise OpenMemoryError(
                    f"OpenMemory request failed: {error_detail}",
                    status_code=response.status_code,
                )

            return response.json()

        except httpx.ConnectError as e:
            logger.error(f"OpenMemory connection failed: {e}")
            raise OpenMemoryUnavailableError(
                "Cannot connect to OpenMemory server"
            ) from e

        except httpx.TimeoutException as e:
            logger.error(f"OpenMemory request timeout: {e}")
            raise OpenMemoryUnavailableError("OpenMemory request timed out") from e

    # ==================== Health & Info ====================

    async def health_check(self) -> dict:
        """
        Check OpenMemory service health.

        Returns:
            Health status dict with status, version, message
        """
        return await self._request("GET", "/health")

    async def get_sectors(self) -> list[str]:
        """
        Get available memory sectors.

        Returns:
            List of sector names
        """
        response = await self._request("GET", "/sectors")
        return response.get("sectors", [])

    # ==================== Memory CRUD ====================

    async def add_memory(
        self,
        agent_id: str,
        content: str,
        sector: str = "semantic",
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        salience: float = 0.5,
        decay_lambda: float | None = None,
    ) -> dict:
        """
        Add memory to the appropriate brain sector.

        Args:
            agent_id: Agent ID (used as user_id for isolation)
            content: Memory content text
            sector: Memory sector (episodic, semantic, procedural, emotional, reflective)
            tags: Optional list of tags
            metadata: Optional metadata dict
            salience: Memory importance (0.0-1.0), default 0.5
            decay_lambda: Custom decay rate (overrides sector default)

        Returns:
            Dict with memory ID and assigned sector
        """
        final_metadata = metadata.copy() if metadata else {}
        # Use primary_sector instead of sector in metadata
        final_metadata["primary_sector"] = sector

        payload: dict[str, Any] = {
            "content": content,
            "user_id": agent_id,
            "tags": tags or [],
            "metadata": final_metadata,
            "salience": salience,
        }

        if decay_lambda is not None:
            payload["decay_lambda"] = decay_lambda

        logger.debug(f"Adding memory for agent {agent_id}: {content[:50]}...")
        logger.debug(f"Add memory payload: {payload}")
        response = await self._request("POST", "/memory/add", json=payload)
        logger.debug(f"Add memory response: {response}")
        return response

    async def get_memory(self, memory_id: str) -> dict:
        """
        Get a single memory by ID.

        Args:
            memory_id: Memory UUID

        Returns:
            Memory entry dict
        """
        return await self._request("GET", f"/memory/{memory_id}")

    async def update_memory(
        self,
        memory_id: str,
        agent_id: str,
        content: str | None = None,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict:
        """
        Update an existing memory.

        Args:
            memory_id: Memory UUID
            agent_id: Agent ID for ownership verification
            content: New content (optional)
            tags: New tags (optional)
            metadata: New metadata (optional)

        Returns:
            Updated memory entry
        """
        payload: dict[str, Any] = {}

        if content is not None:
            payload["content"] = content
        if tags is not None:
            payload["tags"] = tags
        if metadata is not None:
            payload["metadata"] = metadata

        logger.debug(f"Updating memory {memory_id} for agent {agent_id}")
        return await self._request("PATCH", f"/memory/{memory_id}", json=payload)

    async def delete_memory(self, memory_id: str, agent_id: str) -> bool:
        """
        Delete a memory by ID.

        Args:
            memory_id: Memory UUID
            agent_id: Agent ID for ownership verification

        Returns:
            True if deleted successfully
        """
        logger.debug(f"Deleting memory {memory_id} for agent {agent_id}")
        await self._request(
            "DELETE",
            f"/memory/{memory_id}",
            params={"user_id": agent_id},
        )
        return True

    async def list_memories(
        self,
        agent_id: str,
        limit: int = 100,
        offset: int = 0,
        sector: str | None = None,
    ) -> dict:
        """
        Get all memories with pagination.

        Args:
            agent_id: Agent ID
            limit: Maximum memories to return
            offset: Pagination offset
            sector: Optional sector filter

        Returns:
            Dict with items list and pagination info
        """
        url = f"/memory/all?l={limit}&u={offset}&user_id={agent_id}"
        if sector:
            url += f"&sector={sector}"

        logger.debug(f"Listing memories for agent {agent_id}: url={url}")
        response = await self._request("GET", url)
        logger.debug(f"List memories response: {response}")
        return response

    async def get_by_sector(
        self,
        agent_id: str,
        sector: str,
        limit: int = 100,
        offset: int = 0,
    ) -> dict:
        """
        Get memories from a specific brain sector.

        Args:
            agent_id: Agent ID
            sector: Brain sector name
            limit: Maximum memories to return
            offset: Pagination offset

        Returns:
            Dict with memories list
        """
        return await self.list_memories(agent_id, limit, offset, sector)

    # ==================== User Management ====================

    async def get_user_memories(
        self,
        agent_id: str,
        limit: int = 100,
        offset: int = 0,
    ) -> dict:
        """
        Get all memories for a specific user/agent.

        Args:
            agent_id: Agent ID (user_id)
            limit: Maximum memories to return
            offset: Pagination offset

        Returns:
            Dict with user_id and list of memories
        """
        url = f"/users/{agent_id}/memories?l={limit}&u={offset}"
        return await self._request("GET", url)

    async def get_user_summary(self, agent_id: str) -> dict:
        """
        Get user summary with reflection count and last update time.

        Args:
            agent_id: Agent ID (user_id)

        Returns:
            Dict with user_id, summary, reflection_count, updated_at
        """
        return await self._request("GET", f"/users/{agent_id}/summary")

    async def regenerate_user_summary(self, agent_id: str) -> dict:
        """
        Regenerate user summary from their memories.

        Args:
            agent_id: Agent ID (user_id)

        Returns:
            Dict with ok status, user_id, new summary, reflection_count
        """
        return await self._request("POST", f"/users/{agent_id}/summary/regenerate")

    async def delete_user_memories(self, agent_id: str) -> dict:
        """
        Delete all memories for a specific user/agent.

        Args:
            agent_id: Agent ID (user_id)

        Returns:
            Dict with deletion result
        """
        logger.debug(f"Deleting all memories for agent {agent_id}")
        return await self._request("DELETE", f"/users/{agent_id}/memories")

    # ==================== Search ====================

    async def query_memory(
        self,
        agent_id: str,
        query: str,
        k: int = 3,
        min_score: float = 0.5,
        sector: str | None = None,
        tags: list[str] | None = None,
    ) -> dict:
        """
        Query memories with vector similarity search.

        Args:
            agent_id: Agent ID
            query: Search query text
            k: Number of results to return
            min_score: Minimum similarity score threshold
            sector: Specific brain sector to search
            tags: Tag filters

        Returns:
            Dict with query and matched memories (includes sector info)
        """
        filters: dict[str, Any] = {"user_id": agent_id}

        if min_score > 0:
            filters["min_score"] = min_score
        if sector:
            filters["sector"] = sector
        if tags:
            filters["tags"] = tags

        payload = {
            "query": query,
            "k": k,
            "filters": filters,
        }

        logger.debug(f"Querying memories for agent {agent_id}: {query[:50]}...")
        logger.debug(f"Query payload: {payload}")
        response = await self._request("POST", "/memory/query", json=payload)
        logger.debug(f"Query response: {response}")
        return response

    async def query_sector(
        self,
        agent_id: str,
        query: str,
        sector: str,
        k: int = 3,
    ) -> dict:
        """
        Query memories from a specific brain sector.

        Args:
            agent_id: Agent ID
            query: Search query text
            sector: Brain sector ('episodic', 'semantic', 'procedural', 'emotional', 'reflective')
            k: Number of results to return

        Returns:
            Dict with query and matched memories
        """
        return await self.query_memory(agent_id, query, k, sector=sector)

    # ==================== Ingestion ====================

    async def ingest_file(
        self,
        agent_id: str,
        content_type: str,
        data: str,
        filename: str,
        sector: str = "semantic",
        tags: list[str] | None = None,
    ) -> dict:
        """
        Ingest a document file.

        Args:
            agent_id: Agent ID
            content_type: File type (pdf, docx, txt, md)
            data: Base64 encoded file content
            filename: Original filename
            sector: Memory sector for ingested content
            tags: Optional tags for ingested content

        Returns:
            Ingestion result
        """
        payload = {
            "content_type": content_type,
            "data": data,
            "metadata": {
                "filename": filename,
                "sector": sector,
            },
            "user_id": agent_id,
        }

        if tags:
            payload["metadata"]["tags"] = tags

        logger.info(f"Ingesting file {filename} for agent {agent_id}")
        return await self._request("POST", "/memory/ingest", json=payload)

    async def ingest_url(
        self,
        agent_id: str,
        url: str,
        sector: str = "semantic",
        tags: list[str] | None = None,
    ) -> dict:
        """
        Ingest content from a URL.

        Args:
            agent_id: Agent ID
            url: URL to crawl and ingest
            sector: Memory sector for ingested content
            tags: Optional tags for ingested content

        Returns:
            Ingestion result
        """
        payload: dict[str, Any] = {
            "url": url,
            "user_id": agent_id,
        }

        if sector:
            payload["metadata"] = {"sector": sector}
        if tags:
            payload.setdefault("metadata", {})["tags"] = tags

        logger.info(f"Ingesting URL {url} for agent {agent_id}")
        return await self._request("POST", "/memory/ingest/url", json=payload)

    # ==================== Reinforcement ====================

    async def reinforce_memory(
        self,
        memory_id: str,
        boost: float = 0.2,
    ) -> dict:
        """
        Reinforce a memory by increasing its salience.

        Args:
            memory_id: Memory UUID
            boost: Salience boost amount (0.0-1.0), default 0.2

        Returns:
            Dict with reinforcement result
        """
        payload = {"id": memory_id, "boost": boost}
        return await self._request("POST", "/memory/reinforce", json=payload)


# ==================== Singleton ====================

_openmemory_service: OpenMemoryService | None = None


def get_openmemory_service() -> OpenMemoryService:
    """
    Get singleton OpenMemory service instance.

    Returns:
        OpenMemoryService instance configured from settings
    """
    global _openmemory_service

    if _openmemory_service is None:
        _openmemory_service = OpenMemoryService(
            base_url=settings.openmemory.base_url,
            api_key=settings.openmemory.api_key,
            timeout=settings.openmemory.timeout,
        )

    return _openmemory_service


async def close_openmemory_service() -> None:
    """Close the singleton OpenMemory service."""
    global _openmemory_service

    if _openmemory_service:
        await _openmemory_service.close()
        _openmemory_service = None
