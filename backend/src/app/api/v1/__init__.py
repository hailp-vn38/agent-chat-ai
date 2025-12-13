from fastapi import APIRouter

from .auth import router as auth_router
from .health import router as health_router
from .reminder import router as reminder_router, reminder_detail_router
from .users import router as users_router
from .ota import router as ota_router
from .vision import router as vision_router
from .websocket import router as websocket_router
from .agent import router as agent_router
from .template import router as template_router
from .config import router as config_router
from .providers import router as providers_router
from .tools import router as tools_router
from .embeddings import router as embeddings_router
from .knowledge_base import router as knowledge_base_router
from .mcp_configs import router as mcp_configs_router
from .agent_mcp import router as agent_mcp_router
from .system_mcp import router as system_mcp_router

router = APIRouter(prefix="/v1")
router.include_router(health_router)
router.include_router(auth_router)
router.include_router(users_router)

router.include_router(reminder_router)
router.include_router(reminder_detail_router)

router.include_router(ota_router)
router.include_router(vision_router)
router.include_router(websocket_router)
router.include_router(agent_router)
router.include_router(agent_mcp_router)
router.include_router(template_router)
router.include_router(config_router)
router.include_router(providers_router)
router.include_router(tools_router)
router.include_router(embeddings_router)
router.include_router(knowledge_base_router)
router.include_router(mcp_configs_router)
router.include_router(system_mcp_router)
