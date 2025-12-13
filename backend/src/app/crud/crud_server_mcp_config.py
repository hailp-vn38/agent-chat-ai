"""
CRUD operations for ServerMCPConfig model.
"""

from fastcrud import FastCRUD

from ..models.server_mcp_config import ServerMCPConfig
from ..schemas.server_mcp_config import (
    ServerMCPConfigCreate,
    ServerMCPConfigRead,
    ServerMCPConfigUpdate,
)


CRUDServerMCPConfig = FastCRUD[
    ServerMCPConfig,
    ServerMCPConfigCreate,
    ServerMCPConfigUpdate,
    ServerMCPConfigUpdate,
    ServerMCPConfigRead,
    ServerMCPConfigRead,
]

crud_server_mcp_config = CRUDServerMCPConfig(ServerMCPConfig)
