"""Provider API router.

Exposes endpoints to:
- Get provider schemas for UI rendering
- Validate provider configs
- Test provider connections
- CRUD operations for user-defined providers
"""

import logging
from datetime import datetime, timezone
from typing import Annotated, Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.base import PaginatedResponse

from ...api.dependencies import get_current_user
from ...config import load_config
from ...core.db.database import async_get_db
from ...core.exceptions.http_exceptions import NotFoundException
from ...core.logger import get_logger
from ...crud.crud_provider import crud_provider
from ...schemas.provider import (
    ProviderCategory,
    ProviderSourceFilter,
    ProviderCreate,
    ProviderCreateInternal,
    ProviderRead,
    ProviderListItem,
    ProviderUpdate,
    ProviderUpdateInternal,
    ProviderTestRequest,
    ProviderTestResponse,
    ProviderValidateRequest,
    ProviderValidateResponse,
    ProviderReferenceValidateRequest,
    ProviderReferenceValidateResponse,
    ProviderReferenceResolvedInfo,
    ProviderTestByReferenceRequest,
    ProviderTestByReferenceResponse,
)
from ...ai.module_factory import parse_provider_reference, normalize_provider_reference
from ...ai.providers.schema_registry import (
    get_all_schemas,
    get_category_schemas,
    get_provider_schema,
    list_categories,
    list_provider_types,
    FieldType,
)
from ...ai.providers.schema_validator import validate_provider_config

logger = get_logger(__name__)
LOGGER = logging.getLogger(__name__)

router = APIRouter(prefix="/providers", tags=["providers"])

# Danh sách các module categories
MODULE_KEYS = ["LLM", "VLLM", "TTS", "Memory", "Intent", "ASR"]


# ========== Config Endpoints ==========


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

        # Group providers by category with reference field
        for provider in providers:
            category = provider.category
            if category in result:
                result[category].append(
                    {
                        "reference": f"db:{provider.id}",
                        "id": provider.id,
                        "name": provider.name,
                        "type": provider.type,
                        "source": "user",
                        "permissions": ["read", "test", "edit", "delete"],
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
                            for key, cfg in module_config.items():
                                # Get type from config, fallback to key name
                                provider_type = (
                                    cfg.get("type", key)
                                    if isinstance(cfg, dict)
                                    else key
                                )
                                result[module_key].append(
                                    {
                                        "reference": f"config:{key}",
                                        "name": key,
                                        "type": provider_type,
                                        "source": "default",
                                        "permissions": [
                                            "read",
                                            "test",
                                        ],  # Config providers: read-only + test
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


# ========== Helper Functions ==========


def mask_secrets(
    config: dict[str, Any], category: str, provider_type: str
) -> dict[str, Any]:
    """Mask secret fields in config for API response."""
    schema = get_provider_schema(category, provider_type)
    if not schema:
        return config

    masked = config.copy()
    # for field in schema.fields:
    #     if field.type == FieldType.SECRET and field.name in masked:
    #         masked[field.name] = "***"

    return masked


async def verify_provider_ownership(
    db: AsyncSession,
    provider_id: str,
    user_id: str,
) -> ProviderRead:
    """
    Return the requested provider if it belongs to the provided user.

    Raises:
        NotFoundException: If the provider does not exist for the user
    """
    provider = await crud_provider.get(
        db=db,
        id=provider_id,
        user_id=user_id,
        is_deleted=False,
        schema_to_select=ProviderRead,
        return_as_model=True,
    )

    if not provider:
        raise NotFoundException(f"Provider {provider_id} not found")

    return provider


# ========== Schema Endpoints ==========


@router.get("/schemas", tags=["schemas"])
async def get_all_provider_schemas() -> dict[str, Any]:
    """
    Get all provider schemas for UI rendering.

    Returns nested structure:
    {
        "LLM": {"openai": {...}, "gemini": {...}},
        "TTS": {"edge": {...}, "google": {...}},
        ...
    }
    """
    schemas = get_all_schemas()
    return {
        category: {ptype: schema.model_dump() for ptype, schema in types.items()}
        for category, types in schemas.items()
    }


@router.get("/schemas/categories", tags=["schemas"])
async def get_schema_categories() -> dict[str, Any]:
    """
    Get all provider categories with full schema data for each type.

    Returns:
        {
            "categories": ["LLM", "TTS", "ASR"],
            "data": {
                "LLM": {"openai": {...}, "gemini": {...}},
                "TTS": {"edge": {...}, "google": {...}},
                ...
            }
        }
    """
    schemas = get_all_schemas()
    return {
        "categories": list(schemas.keys()),
        "data": {
            category: {ptype: schema.model_dump() for ptype, schema in types.items()}
            for category, types in schemas.items()
        },
    }


# ========== Validation Endpoints ==========


@router.post("/validate", response_model=ProviderValidateResponse, tags=["validation"])
async def validate_provider(
    request: ProviderValidateRequest,
) -> ProviderValidateResponse:
    """
    Validate provider config against schema (without saving or testing).

    Returns validation result with normalized config if valid.
    """
    is_valid, normalized, errors = validate_provider_config(
        category=request.category.value,
        provider_type=request.type,
        config=request.config,
    )

    return ProviderValidateResponse(
        valid=is_valid,
        normalized_config=normalized if is_valid else None,
        errors=errors,
    )


@router.post(
    "/validate-reference",
    response_model=ProviderReferenceValidateResponse,
    tags=["validation"],
)
async def validate_provider_reference(
    request: ProviderReferenceValidateRequest,
    db: Annotated[AsyncSession, Depends(async_get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
) -> ProviderReferenceValidateResponse:
    """
    Validate provider reference format and check if provider exists.

    Reference formats:
    - "config:{name}" - Provider from config.yml
    - "db:{uuid}" - Provider from database

    Returns validation result with resolved provider info if valid.
    """
    reference = request.reference
    category = request.category.value
    errors: list[str] = []

    # Try to normalize/parse reference
    try:
        normalized = normalize_provider_reference(reference)
    except ValueError as e:
        return ProviderReferenceValidateResponse(
            valid=False,
            reference=reference,
            resolved=None,
            errors=[str(e)],
        )

    parsed = parse_provider_reference(normalized)
    if parsed is None:
        return ProviderReferenceValidateResponse(
            valid=False,
            reference=reference,
            resolved=None,
            errors=["Invalid provider reference format"],
        )

    source, value = parsed

    if source == "config":
        # Validate config provider exists
        try:
            config = load_config()
            if category not in config:
                errors.append(f"Category '{category}' not found in config")
            elif value not in config[category]:
                errors.append(
                    f"Provider '{value}' not found in config.yml for category '{category}'"
                )
            else:
                # Valid config provider
                cfg = config[category][value]
                provider_type = (
                    cfg.get("type", value) if isinstance(cfg, dict) else value
                )
                return ProviderReferenceValidateResponse(
                    valid=True,
                    reference=normalized,
                    resolved=ProviderReferenceResolvedInfo(
                        name=value,
                        type=provider_type,
                        source="default",
                    ),
                    errors=[],
                )
        except Exception as e:
            errors.append(f"Failed to load config: {str(e)}")

    elif source == "db":
        # Validate db provider exists and belongs to user
        user_id = current_user.get("sub") or current_user.get("id")
        try:
            provider = await crud_provider.get(
                db=db,
                id=value,
                user_id=user_id,
                is_deleted=False,
                schema_to_select=ProviderRead,
                return_as_model=True,
            )
            if provider is None:
                errors.append(
                    f"Provider '{value}' not found or does not belong to user"
                )
            elif provider.category != category:
                errors.append(
                    f"Provider '{value}' is category '{provider.category}', expected '{category}'"
                )
            else:
                # Valid db provider
                return ProviderReferenceValidateResponse(
                    valid=True,
                    reference=normalized,
                    resolved=ProviderReferenceResolvedInfo(
                        name=provider.name,
                        type=provider.type,
                        source="user",
                    ),
                    errors=[],
                )
        except Exception as e:
            errors.append(f"Failed to query provider: {str(e)}")

    return ProviderReferenceValidateResponse(
        valid=False,
        reference=normalized if normalized else reference,
        resolved=None,
        errors=errors,
    )


@router.post("/test", response_model=ProviderTestResponse, tags=["validation"])
async def test_provider(
    request: ProviderTestRequest,
) -> ProviderTestResponse:
    """
    Test provider config by validating schema AND making actual API call.

    1. Validates config against schema
    2. Creates temporary provider instance
    3. Makes minimal API call to verify connectivity
    4. Returns test result with latency info

    Optional `input_data` can be provided for custom test inputs:
    - ASR: `audio_base64` (base64-encoded audio)
    - TTS: `text` (custom text to synthesize)
    - LLM: `prompt` (custom prompt)
    - VLLM: `image_base64` + `question`

    If `input_data` is not provided, default test data is used.
    """
    # Step 1: Validate schema
    is_valid, normalized, errors = validate_provider_config(
        category=request.category.value,
        provider_type=request.type,
        config=request.config,
    )

    if not is_valid:
        return ProviderTestResponse(
            valid=False,
            errors=errors,
            test_result=None,
        )

    # Step 2: Test provider connection
    # Import here to avoid circular imports
    from ...ai.providers.provider_tester import test_provider_connection

    test_result = await test_provider_connection(
        category=request.category.value,
        provider_type=request.type,
        config=normalized,
        input_data=request.input_data,
    )

    return ProviderTestResponse(
        valid=True,
        normalized_config=normalized,
        errors=[],
        test_result=test_result,
    )


@router.post(
    "/test-reference",
    response_model=ProviderTestByReferenceResponse,
    tags=["validation"],
)
async def test_provider_by_reference(
    db: Annotated[AsyncSession, Depends(async_get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
    request: ProviderTestByReferenceRequest,
) -> ProviderTestByReferenceResponse:
    """
    Test provider by reference string.

    Supports:
    - "config:{name}" - test config provider from config.yml
    - "db:{uuid}" or plain UUID - test user's provider from database

    Optional `input_data` can be provided for custom test inputs:
    - ASR: `audio_base64` (base64-encoded audio)
    - TTS: `text` (custom text to synthesize)
    - LLM: `prompt` (custom prompt)
    - VLLM: `image_base64` + `question`

    If `input_data` is not provided, default test data is used.
    """
    from ...ai.providers.provider_tester import test_provider_connection

    errors: list[str] = []

    # Parse reference
    parsed = parse_provider_reference(request.reference)
    if parsed is None:
        return ProviderTestByReferenceResponse(
            valid=False,
            reference=request.reference,
            errors=[f"Invalid provider reference format: {request.reference}"],
        )

    source, value = parsed
    provider_config: dict[str, Any] = {}
    category: str | None = None
    provider_type: str | None = None
    source_label: str | None = None

    if source == "config":
        # Load from config.yml
        try:
            config = load_config()
            found = False
            for cat in MODULE_KEYS:
                if cat in config and isinstance(config[cat], dict):
                    if value in config[cat]:
                        cfg = config[cat][value]
                        category = cat
                        provider_type = (
                            cfg.get("type", value) if isinstance(cfg, dict) else value
                        )
                        provider_config = cfg if isinstance(cfg, dict) else {}
                        provider_config["type"] = provider_type
                        source_label = "default"
                        found = True
                        break

            if not found:
                return ProviderTestByReferenceResponse(
                    valid=False,
                    reference=request.reference,
                    errors=[f"Config provider '{value}' not found"],
                )
        except Exception as e:
            return ProviderTestByReferenceResponse(
                valid=False,
                reference=request.reference,
                errors=[f"Failed to load config: {str(e)}"],
            )

    else:
        # source == "db" - fetch from database
        user_id = current_user["id"]
        try:
            provider = await crud_provider.get(
                db=db,
                id=value,
                user_id=user_id,
                is_deleted=False,
                schema_to_select=ProviderRead,
                return_as_model=True,
            )
            if not provider:
                return ProviderTestByReferenceResponse(
                    valid=False,
                    reference=request.reference,
                    errors=[f"Provider '{value}' not found or does not belong to user"],
                )

            category = provider.category
            provider_type = provider.type
            provider_config = {**provider.config, "type": provider.type}
            source_label = "user"
        except Exception as e:
            return ProviderTestByReferenceResponse(
                valid=False,
                reference=request.reference,
                errors=[f"Failed to fetch provider: {str(e)}"],
            )

    # Run test
    try:
        test_result = await test_provider_connection(
            category=category,
            provider_type=provider_type,
            config=provider_config,
            input_data=request.input_data,
        )

        return ProviderTestByReferenceResponse(
            valid=True,
            reference=request.reference,
            source=source_label,
            category=category,
            type=provider_type,
            errors=[],
            test_result=test_result,
        )
    except Exception as e:
        return ProviderTestByReferenceResponse(
            valid=False,
            reference=request.reference,
            source=source_label,
            category=category,
            type=provider_type,
            errors=[f"Test failed: {str(e)}"],
        )


# ========== CRUD Endpoints ==========


def _load_config_providers(category: ProviderCategory | None) -> list[dict[str, Any]]:
    """Load config providers from config.yml with optional category filter."""
    config_providers = []
    try:
        config = load_config()
        categories_to_check = [category.value] if category else MODULE_KEYS

        for cat in categories_to_check:
            if cat not in config or not isinstance(config[cat], dict):
                continue

            for name, cfg in config[cat].items():
                provider_type = cfg.get("type", name) if isinstance(cfg, dict) else name
                config_providers.append(
                    {
                        "reference": f"config:{name}",
                        "name": name,
                        "category": cat,
                        "type": provider_type,
                        "config": mask_secrets(
                            cfg if isinstance(cfg, dict) else {},
                            cat,
                            provider_type,
                        ),
                        "source": "default",
                        "permissions": ["read", "test"],
                        "is_active": True,
                    }
                )
    except Exception as e:
        LOGGER.warning(f"Failed to load config providers: {e}")

    return config_providers


def _format_user_provider(provider: Any) -> dict[str, Any]:
    """Format user provider with masked secrets and metadata."""
    p_dict = (
        provider.model_dump() if hasattr(provider, "model_dump") else dict(provider)
    )
    p_dict["config"] = mask_secrets(
        p_dict["config"], p_dict["category"], p_dict["type"]
    )
    p_dict["reference"] = f"db:{p_dict['id']}"
    p_dict["source"] = "user"
    p_dict["permissions"] = ["read", "test", "edit", "delete"]
    return p_dict


@router.get("", response_model=PaginatedResponse[ProviderListItem])
async def list_providers(
    db: Annotated[AsyncSession, Depends(async_get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
    category: Annotated[ProviderCategory | None, Query()] = None,
    source: Annotated[
        ProviderSourceFilter,
        Query(description="Filter by source: all, config, user"),
    ] = ProviderSourceFilter.USER,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 10,
) -> dict[str, Any]:
    """
    List providers with proper pagination.

    Args:
        category: Optional filter by category (LLM, TTS, ASR, etc.)
        source: Filter by source - all (config + user), config, user (default)
        page: Page number (1-indexed)
        page_size: Items per page (max 100)

    Returns:
        Paginated list of providers.
        - source=all: Config providers first, then user providers (proper pagination)
        - source=config: Only config.yml providers
        - source=user: Only user-defined providers
    """
    user_id = current_user["id"]
    offset = (page - 1) * page_size

    # Case 1: Only config providers
    if source == ProviderSourceFilter.CONFIG:
        config_providers = _load_config_providers(category)
        total = len(config_providers)
        data = config_providers[offset : offset + page_size]
        total_pages = (total + page_size - 1) // page_size if total > 0 else 0

        return {
            "success": True,
            "message": "Success",
            "data": data,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
        }

    # Build filters for user providers
    filters = {"user_id": user_id, "is_deleted": False}
    if category:
        filters["category"] = category.value

    # Case 2: Only user providers
    if source == ProviderSourceFilter.USER:
        result = await crud_provider.get_multi(
            db=db,
            offset=offset,
            limit=page_size,
            schema_to_select=ProviderRead,
            return_as_model=True,
            **filters,
        )

        providers = result.get("data", [])
        total = result.get("total_count", 0)
        data = [_format_user_provider(p) for p in providers]
        total_pages = (total + page_size - 1) // page_size if total > 0 else 0

        return {
            "success": True,
            "message": "Success",
            "data": data,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
        }

    # Case 3: All providers (config first, then user) with hybrid pagination
    config_providers = _load_config_providers(category)
    config_count = len(config_providers)

    # Get total user providers count
    user_count_result = await crud_provider.count(db=db, **filters)
    user_count = user_count_result if isinstance(user_count_result, int) else 0
    total = config_count + user_count

    data: list[dict[str, Any]] = []

    if offset < config_count:
        # Page includes config providers
        config_slice = config_providers[offset : offset + page_size]
        data.extend(config_slice)

        remaining = page_size - len(config_slice)
        if remaining > 0:
            # Need user providers to fill the page
            user_result = await crud_provider.get_multi(
                db=db,
                offset=0,
                limit=remaining,
                schema_to_select=ProviderRead,
                return_as_model=True,
                **filters,
            )
            user_providers = user_result.get("data", [])
            data.extend([_format_user_provider(p) for p in user_providers])
    else:
        # Page is entirely in user providers
        user_offset = offset - config_count
        user_result = await crud_provider.get_multi(
            db=db,
            offset=user_offset,
            limit=page_size,
            schema_to_select=ProviderRead,
            return_as_model=True,
            **filters,
        )
        user_providers = user_result.get("data", [])
        data = [_format_user_provider(p) for p in user_providers]

    total_pages = (total + page_size - 1) // page_size if total > 0 else 0

    return {
        "success": True,
        "message": "Success",
        "data": data,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
    }


@router.post("", response_model=ProviderRead, status_code=201)
async def create_provider(
    db: Annotated[AsyncSession, Depends(async_get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
    provider: ProviderCreate,
) -> ProviderRead:
    """
    Create a new provider.

    Config is validated against schema before saving.
    """
    user_id = current_user["id"]

    # Validate config
    is_valid, normalized, errors = validate_provider_config(
        category=provider.category.value,
        provider_type=provider.type,
        config=provider.config,
    )

    if not is_valid:
        raise HTTPException(status_code=400, detail={"errors": errors})

    # Create provider
    provider_internal = ProviderCreateInternal(
        user_id=user_id,
        name=provider.name,
        category=provider.category,
        type=provider.type,
        config=normalized,
        is_active=provider.is_active,
    )

    created = await crud_provider.create(
        db=db,
        object=provider_internal,
        schema_to_select=ProviderRead,
        return_as_model=True,
    )

    # Convert ORM object to dict for response
    created_dict = {
        "id": created.id,
        "user_id": created.user_id,
        "name": created.name,
        "category": created.category,
        "type": created.type,
        "config": created.config,
        "is_active": created.is_active,
        "created_at": created.created_at,
        "updated_at": created.updated_at,
        "is_deleted": created.is_deleted,
    }

    # Mask secrets in response
    created_dict["config"] = mask_secrets(
        created_dict["config"],
        created_dict["category"],
        created_dict["type"],
    )

    return created_dict


@router.get("/{reference}", response_model=None)
async def get_provider(
    db: Annotated[AsyncSession, Depends(async_get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
    reference: str,
) -> dict[str, Any]:
    """
    Get a provider by reference.

    Supports both:
    - "db:{uuid}" or plain UUID - fetch from database
    - "config:{name}" - fetch from config.yml

    Secret fields are masked in response.
    """
    from ...ai.module_factory import parse_provider_reference

    parsed = parse_provider_reference(reference)
    if parsed is None:
        raise HTTPException(
            status_code=400, detail=f"Invalid provider reference format: {reference}"
        )

    source, value = parsed

    if source == "config":
        # Fetch from config.yml
        config = load_config()

        # Find provider in config by iterating categories
        for category in MODULE_KEYS:
            if category in config and isinstance(config[category], dict):
                if value in config[category]:
                    provider_config = config[category][value]
                    provider_type = (
                        provider_config.get("type", value)
                        if isinstance(provider_config, dict)
                        else value
                    )
                    return {
                        "reference": f"config:{value}",
                        "name": value,
                        "category": category,
                        "type": provider_type,
                        "config": mask_secrets(
                            (
                                provider_config
                                if isinstance(provider_config, dict)
                                else {}
                            ),
                            category,
                            provider_type,
                        ),
                        "source": "default",
                        "permissions": ["read", "test"],
                    }

        raise NotFoundException(f"Config provider '{value}' not found")

    else:
        # Fetch from database (source == "db")
        user_id = current_user["id"]
        provider = await verify_provider_ownership(db, value, user_id)

        result = (
            provider.model_dump() if hasattr(provider, "model_dump") else dict(provider)
        )
        result["config"] = mask_secrets(
            result["config"], result["category"], result["type"]
        )
        result["reference"] = f"db:{result['id']}"
        result["source"] = "user"
        result["permissions"] = ["read", "test", "edit", "delete"]

        return result


@router.put("/{reference}", response_model=ProviderRead)
async def update_provider(
    db: Annotated[AsyncSession, Depends(async_get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
    reference: str,
    update_data: ProviderUpdate,
) -> dict[str, Any]:
    """
    Update a provider.

    Only database providers can be updated.
    Config providers (config:*) are read-only.

    If config is provided, it's validated against schema.
    """
    from ...ai.module_factory import parse_provider_reference

    # Check if it's a config provider
    parsed = parse_provider_reference(reference)
    if parsed is None:
        raise HTTPException(
            status_code=400, detail=f"Invalid provider reference format: {reference}"
        )

    source, value = parsed
    if source == "config":
        raise HTTPException(
            status_code=403,
            detail="Config providers are read-only and cannot be updated",
        )

    # It's a db provider, proceed with update
    provider_id = value
    user_id = current_user["id"]
    existing = await verify_provider_ownership(db, provider_id, user_id)

    # If config is being updated, validate it
    if update_data.config is not None:
        existing_dict = (
            existing.model_dump() if hasattr(existing, "model_dump") else dict(existing)
        )
        is_valid, normalized, errors = validate_provider_config(
            category=existing_dict["category"],
            provider_type=existing_dict["type"],
            config=update_data.config,
        )

        if not is_valid:
            raise HTTPException(status_code=400, detail={"errors": errors})

        update_data.config = normalized

    # Build update dict excluding None values
    update_dict: dict[str, Any] = {"updated_at": datetime.now(timezone.utc)}
    if update_data.name is not None:
        update_dict["name"] = update_data.name
    if update_data.config is not None:
        update_dict["config"] = update_data.config
    if update_data.is_active is not None:
        update_dict["is_active"] = update_data.is_active

    await crud_provider.update(
        db=db,
        object=update_dict,
        id=provider_id,
        user_id=user_id,
    )

    # Get updated provider
    updated = await verify_provider_ownership(db, provider_id, user_id)
    result = updated.model_dump() if hasattr(updated, "model_dump") else dict(updated)
    result["config"] = mask_secrets(
        result["config"], result["category"], result["type"]
    )

    return result


@router.delete("/{reference}", status_code=204)
async def delete_provider(
    db: Annotated[AsyncSession, Depends(async_get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
    reference: str,
) -> None:
    """
    Delete a provider (soft delete).

    Only database providers can be deleted.
    Config providers (config:*) are read-only.
    """
    from ...ai.module_factory import parse_provider_reference

    # Check if it's a config provider
    parsed = parse_provider_reference(reference)
    if parsed is None:
        raise HTTPException(
            status_code=400, detail=f"Invalid provider reference format: {reference}"
        )

    source, value = parsed
    if source == "config":
        raise HTTPException(
            status_code=403,
            detail="Config providers are read-only and cannot be deleted",
        )

    # It's a db provider, proceed with delete
    provider_id = value
    user_id = current_user["id"]
    await verify_provider_ownership(db, provider_id, user_id)

    # Soft delete using FastCRUD's built-in soft delete
    await crud_provider.delete(
        db=db,
        id=provider_id,
    )
