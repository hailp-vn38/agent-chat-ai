"""
CRUD operations for agent MCP selection models.

Uses FastCRUD pattern for standard operations.
"""

from fastcrud import FastCRUD
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.agent_mcp_selection import AgentMCPSelection, AgentMCPServerSelected
from ..schemas.agent import (
    AgentMCPSelectionRead,
    AgentMCPServerSelectedRead,
    AgentMCPSelectionCreate,
    AgentMCPServerSelectedCreate,
)
from ..core.logger import get_logger

logger = get_logger(__name__)


class CRUDAgentMCPSelection(
    FastCRUD[
        AgentMCPSelection,
        AgentMCPSelectionCreate,
        dict,
        dict,
        dict,
        AgentMCPSelectionRead,
    ]
):
    """CRUD operations for agent_mcp_selection table."""

    async def get_joined(
        self,
        db: AsyncSession,
        **filters,
    ):
        """Get selection with servers joined."""
        selection = await self.get(
            db=db,
            schema_to_select=AgentMCPSelectionRead,
            return_as_model=True,
            **filters,
        )

        if not selection:
            return None

        # Fetch servers for this selection
        servers_result = await crud_agent_mcp_server_selected.get_multi(
            db=db,
            agent_mcp_selection_id=selection.id,
            schema_to_select=AgentMCPServerSelectedRead,
        )

        # Update selection with servers
        servers = [
            AgentMCPServerSelectedRead(**server) if isinstance(server, dict) else server
            for server in servers_result.get("data", [])
        ]

        # Reconstruct with servers included
        return AgentMCPSelectionRead(
            id=selection.id,
            agent_id=selection.agent_id,
            mcp_selection_mode=selection.mcp_selection_mode,
            servers=servers,
            created_at=selection.created_at,
            updated_at=selection.updated_at,
        )


class CRUDAgentMCPServerSelected(
    FastCRUD[
        AgentMCPServerSelected,
        AgentMCPServerSelectedCreate,
        dict,
        dict,
        dict,
        AgentMCPServerSelectedRead,
    ]
):
    """CRUD operations for agent_mcp_server_selected table."""

    async def delete_multi(self, db: AsyncSession, **filters):
        """Delete multiple records matching filters."""
        return await self.delete(db=db, allow_multiple=True, **filters)


crud_agent_mcp_selection = CRUDAgentMCPSelection(AgentMCPSelection)
crud_agent_mcp_server_selected = CRUDAgentMCPServerSelected(AgentMCPServerSelected)
