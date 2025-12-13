"""
Config Endpoint - Lấy danh sách các module/provider có sẵn cho user
+ Admin endpoint để update runtime config
"""

import logging
from copy import deepcopy
from typing import Annotated, Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from ...config import load_config, Settings
from ...config import config_loader as _config_loader_module
from ...core.db.database import async_get_db
from ..dependencies import get_current_user, get_current_superuser
from ...crud.crud_provider import crud_provider
from ...schemas.provider import ProviderRead

router = APIRouter(tags=["config"])


# ========== Schemas for Config Update ==========


class ServerConfigUpdate(BaseModel):
    """Partial update schema cho server config"""

    ip: Optional[str] = None
    port: Optional[int] = Field(None, ge=1, le=65535)
    http_port: Optional[int] = Field(None, ge=1, le=65535)
    auth_key: Optional[str] = None
    tz: Optional[str] = None

    model_config = {"extra": "allow"}


class AuthConfigUpdate(BaseModel):
    """Partial update schema cho auth config"""

    enabled: Optional[bool] = None
    allowed_devices: Optional[List[str]] = None
    expire_seconds: Optional[int] = Field(None, ge=60)

    model_config = {"extra": "allow"}


class ReminderMQTTUpdate(BaseModel):
    """Partial update schema cho reminder MQTT"""

    tts_mqtt_url: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    topic_base: Optional[str] = None

    model_config = {"extra": "allow"}


class ReminderConfigUpdate(BaseModel):
    """Partial update schema cho reminder config"""

    mqtt: Optional[ReminderMQTTUpdate] = None
    service_key: Optional[str] = None
    prompt: Optional[str] = None

    model_config = {"extra": "allow"}


class OpenMemoryConfigUpdate(BaseModel):
    """Partial update schema cho OpenMemory config"""

    base_url: Optional[str] = None
    api_key: Optional[str] = None
    timeout: Optional[int] = Field(None, ge=1, le=300)
    enabled: Optional[bool] = None

    model_config = {"extra": "allow"}


class ConfigUpdate(BaseModel):
    """
    Schema cho partial update runtime config.

    Chỉ cần truyền các fields cần update, những fields không truyền sẽ giữ nguyên.
    """

    server: Optional[ServerConfigUpdate] = None
    auth: Optional[AuthConfigUpdate] = None
    selected_module: Optional[Dict[str, str]] = None
    reminder: Optional[ReminderConfigUpdate] = None
    openmemory: Optional[OpenMemoryConfigUpdate] = None
    read_config_from_api: Optional[bool] = None
    mcp_endpoint: Optional[str] = None
    exit_commands: Optional[List[str]] = None
    close_connection_no_voice_time: Optional[int] = Field(None, ge=30, le=3600)
    prompt: Optional[str] = None
    delete_audio: Optional[bool] = None

    # Cho phép extra fields (LLM, TTS, ASR, etc.)
    model_config = {"extra": "allow"}

    @field_validator("selected_module", mode="before")
    @classmethod
    def validate_selected_module(cls, v):
        if v is None:
            return v
        if not isinstance(v, dict):
            raise ValueError("selected_module phải là dict")
        valid_keys = {"VAD", "ASR", "LLM", "VLLM", "TTS", "Memory", "Intent"}
        for key in v.keys():
            if key not in valid_keys:
                raise ValueError(f"Invalid module key: {key}. Valid: {valid_keys}")
        return v


class ConfigResponse(BaseModel):
    """Response schema cho config"""

    success: bool = True
    message: str = "Config updated successfully"
    updated_keys: List[str] = Field(default_factory=list)
    config: Optional[Dict[str, Any]] = None


# ========== Helper Functions ==========


def deep_merge(base: Dict[str, Any], updates: Dict[str, Any]) -> Dict[str, Any]:
    """
    Deep merge updates vào base dict.

    - Nested dicts được merge recursively
    - Lists được replace hoàn toàn
    - None values trong updates sẽ bị bỏ qua (không xóa key)
    """
    result = deepcopy(base)

    for key, value in updates.items():
        if value is None:
            continue  # Bỏ qua None values

        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            # Recursive merge cho nested dicts
            result[key] = deep_merge(result[key], value)
        else:
            # Replace value
            result[key] = deepcopy(value)

    return result


def extract_updated_keys(updates: Dict[str, Any], prefix: str = "") -> List[str]:
    """Extract list of updated keys từ update dict (flatten nested keys)"""
    keys = []
    for key, value in updates.items():
        if value is None:
            continue
        full_key = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            keys.extend(extract_updated_keys(value, full_key))
        else:
            keys.append(full_key)
    return keys


LOGGER = logging.getLogger(__name__)

# Danh sách các module categories
MODULE_KEYS = ["LLM", "VLLM", "TTS", "Memory", "Intent", "ASR"]


@router.get(
    "/config/modules",
    status_code=status.HTTP_200_OK,
    summary="Get available modules/providers for current user",
    description="Trả về danh sách providers của user grouped by category. Nếu include_defaults=true thì kèm cả config.yml defaults.",
)
async def get_config_modules(
    db: Annotated[AsyncSession, Depends(async_get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
    include_defaults: bool = Query(
        default=False,
        description="Include default modules from config.yml",
    ),
) -> Dict[str, List[Any]]:
    """
    Lấy danh sách providers của user grouped by category.

    Response example (include_defaults=false):
    ```json
    {
        "LLM": [
            {"id": "uuid-1", "name": "My GPT-4", "type": "openai", "source": "user"},
            {"id": "uuid-2", "name": "My Gemini", "type": "gemini", "source": "user"}
        ],
        "TTS": [
            {"id": "uuid-3", "name": "My Edge TTS", "type": "edge", "source": "user"}
        ],
        "ASR": [],
        ...
    }
    ```

    Response example (include_defaults=true):
    ```json
    {
        "LLM": [
            {"id": "uuid-1", "name": "My GPT-4", "type": "openai", "source": "user"},
            {"name": "CopilotLLM", "source": "default"},
            {"name": "GPT5miniLLM", "source": "default"}
        ],
        ...
    }
    ```
    """
    try:
        user_id = current_user.get("sub") or current_user.get("id")
        result: Dict[str, List[Any]] = {key: [] for key in MODULE_KEYS}

        # Query user's providers from database
        providers_result = await crud_provider.get_multi(
            db=db,
            user_id=user_id,
            is_deleted=False,
            is_active=True,
            schema_to_select=ProviderRead,
            return_as_model=True,
        )
        providers = providers_result.get("data", [])

        # Group providers by category
        for provider in providers:
            category = provider.category
            if category in result:
                result[category].append(
                    {
                        "id": provider.id,
                        "name": provider.name,
                        "type": provider.type,
                        "source": "user",
                    }
                )

        # Include defaults from config.yml if requested
        if include_defaults:
            try:
                config = load_config()
                for module_key in MODULE_KEYS:
                    if module_key in config:
                        module_config = config[module_key]
                        if isinstance(module_config, dict):
                            for key in module_config.keys():
                                result[module_key].append(
                                    {
                                        "name": key,
                                        "source": "default",
                                    }
                                )
            except Exception as config_err:
                LOGGER.warning(f"Failed to load config defaults: {config_err}")

        return JSONResponse(status_code=status.HTTP_200_OK, content=result)

    except Exception as exc:
        LOGGER.error(f"Error loading config modules: {exc}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"error": f"Failed to load modules: {str(exc)}"},
        )


# ========== Admin Config Management Endpoints ==========


@router.get(
    "/admin/config",
    status_code=status.HTTP_200_OK,
    summary="[Admin] Get current runtime config",
    description="Lấy config đang chạy hiện tại (runtime). Chỉ admin mới có quyền.",
    response_model=ConfigResponse,
)
async def get_runtime_config(
    request: Request,
    current_user: Annotated[dict, Depends(get_current_superuser)],
    include_sensitive: bool = Query(
        default=False,
        description="Include sensitive fields (api_key, password, etc.)",
    ),
) -> ConfigResponse:
    """
    Lấy config runtime hiện tại.

    - Mặc định mask các sensitive fields
    - Truyền include_sensitive=true để xem đầy đủ
    """
    try:
        settings: Settings = request.app.state.config
        config_dict = settings.to_dict()

        if not include_sensitive:
            config_dict = _mask_sensitive_fields(deepcopy(config_dict))

        return ConfigResponse(
            success=True,
            message="Current runtime config",
            config=config_dict,
        )
    except Exception as exc:
        LOGGER.error(f"Error getting runtime config: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get config: {str(exc)}",
        )


@router.patch(
    "/admin/config",
    status_code=status.HTTP_200_OK,
    summary="[Admin] Update runtime config",
    description="Update config runtime (không persist xuống file). Chỉ admin mới có quyền.",
    response_model=ConfigResponse,
)
async def update_runtime_config(
    request: Request,
    config_update: ConfigUpdate,
    current_user: Annotated[dict, Depends(get_current_superuser)],
) -> ConfigResponse:
    """
    Update runtime config (partial update).

    - Chỉ update các fields được truyền
    - Nested objects được merge (không replace hoàn toàn)
    - Không persist xuống file, restart server sẽ mất changes
    - Connection mới sẽ nhận config mới, connection đang active giữ nguyên

    Example request:
    ```json
    {
        "server": {"port": 9000},
        "selected_module": {"LLM": "LLM_gemini"},
        "close_connection_no_voice_time": 180
    }
    ```
    """
    try:
        # 1. Get current settings
        settings: Settings = request.app.state.config
        current_config = settings.to_dict()

        # 2. Convert update to dict (exclude None values)
        update_dict = config_update.model_dump(exclude_none=True)

        if not update_dict:
            return ConfigResponse(
                success=True,
                message="No changes provided",
                updated_keys=[],
            )

        # 3. Deep merge updates into current config
        merged_config = deep_merge(current_config, update_dict)

        # 4. Validate merged config by creating new Settings
        try:
            new_settings = Settings.from_dict(merged_config)
        except Exception as validation_error:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Config validation failed: {str(validation_error)}",
            )

        # 5. Update runtime config
        request.app.state.config = new_settings

        # 6. Invalidate global cache để load_config() trả về merged config
        with _config_loader_module._CACHE_LOCK:
            _config_loader_module._CONFIG_CACHE = merged_config

        # 7. Extract updated keys for response
        updated_keys = extract_updated_keys(update_dict)

        LOGGER.info(
            f"[Admin Config] User {current_user.get('email')} updated config: {updated_keys}"
        )

        return ConfigResponse(
            success=True,
            message="Config updated successfully (runtime only)",
            updated_keys=updated_keys,
            config=_mask_sensitive_fields(deepcopy(merged_config)),
        )

    except HTTPException:
        raise
    except Exception as exc:
        LOGGER.error(f"Error updating runtime config: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update config: {str(exc)}",
        )


@router.post(
    "/admin/config/reload",
    status_code=status.HTTP_200_OK,
    summary="[Admin] Reload config from files",
    description="Force reload config từ YAML files (base + override). Chỉ admin mới có quyền.",
    response_model=ConfigResponse,
)
async def reload_config_from_files(
    request: Request,
    current_user: Annotated[dict, Depends(get_current_superuser)],
) -> ConfigResponse:
    """
    Force reload config từ YAML files.

    - Đọc lại từ config.yml và .config.yml
    - Merge và update runtime config
    - Hữu ích sau khi edit file config thủ công
    """
    try:
        # Force reload from files
        raw_config = load_config(force_reload=True)

        # Create new settings
        new_settings = Settings.from_dict(raw_config)

        # Update runtime
        request.app.state.config = new_settings

        LOGGER.info(
            f"[Admin Config] User {current_user.get('email')} reloaded config from files"
        )

        return ConfigResponse(
            success=True,
            message="Config reloaded from files successfully",
            config=_mask_sensitive_fields(deepcopy(raw_config)),
        )

    except Exception as exc:
        LOGGER.error(f"Error reloading config: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to reload config: {str(exc)}",
        )


def _mask_sensitive_fields(config: Dict[str, Any]) -> Dict[str, Any]:
    """Mask các fields nhạy cảm trong config"""
    sensitive_keys = {
        "api_key",
        "auth_key",
        "password",
        "secret",
        "token",
        "key",
        "secret_key",
        "access_key",
        "private_key",
    }

    def _mask_recursive(obj: Any, parent_key: str = "") -> Any:
        if isinstance(obj, dict):
            return {k: _mask_recursive(v, k) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [_mask_recursive(item, parent_key) for item in obj]
        elif parent_key.lower() in sensitive_keys and isinstance(obj, str) and obj:
            # Mask value nhưng giữ 4 ký tự cuối
            if len(obj) > 8:
                return f"***{obj[-4:]}"
            return "***"
        return obj

    return _mask_recursive(config)
