"""
Provider Schema Validator - Validate provider configs against schema registry.
"""

import re
from typing import Any

from app.ai.providers.schema_registry import (
    FieldType,
    ProviderFieldSchema,
    get_provider_schema,
)


def validate_provider_config(
    category: str,
    provider_type: str,
    config: dict[str, Any],
) -> tuple[bool, dict[str, Any], list[str]]:
    """
    Validate và normalize config theo schema.

    Args:
        category: Provider category (LLM, TTS, ASR)
        provider_type: Provider type (openai, gemini, edge, etc.)
        config: Raw config dict từ user

    Returns:
        Tuple of (is_valid, normalized_config, errors)
        - is_valid: True nếu config hợp lệ
        - normalized_config: Config đã normalize với defaults
        - errors: List các lỗi validation
    """
    errors: list[str] = []
    normalized: dict[str, Any] = {"type": provider_type}

    # Get schema
    schema = get_provider_schema(category, provider_type)
    if schema is None:
        return False, {}, [f"Unknown provider: {category}/{provider_type}"]

    # Special validation for Intent provider function_call type
    if category == "Intent" and provider_type == "function_call":
        intent_errors = _validate_intent_functions(config.get("functions", []))
        if intent_errors:
            errors.extend(intent_errors)

    # Validate each field
    for field in schema.fields:
        value = config.get(field.name)
        validated_value, field_errors = _validate_field(field, value)

        if field_errors:
            errors.extend(field_errors)
        else:
            normalized[field.name] = validated_value

    is_valid = len(errors) == 0
    return is_valid, normalized if is_valid else {}, errors


def _validate_intent_functions(functions: Any) -> list[str]:
    """
    Validate Intent provider function names.

    Ensures all function names exist in the system registry.
    Only system function names are accepted (no UUID references).

    Args:
        functions: List of function names from config

    Returns:
        List of validation errors (empty if valid)
    """
    from app.ai.plugins_func.register import all_function_registry

    errors: list[str] = []

    # If functions is empty or None, it's valid (uses all available)
    if not functions:
        return []

    # Ensure it's a list
    if not isinstance(functions, list):
        return ["Field 'functions' must be a list"]

    # Check each function name exists in registry
    for func_name in functions:
        if not isinstance(func_name, str):
            errors.append(
                f"Function name must be a string, got {type(func_name).__name__}"
            )
            continue

        if func_name not in all_function_registry:
            errors.append(f"Function '{func_name}' not found in system registry")

    return errors


def _validate_field(
    field: ProviderFieldSchema,
    value: Any,
) -> tuple[Any, list[str]]:
    """
    Validate a single field value.

    Returns:
        Tuple of (validated_value, errors)
    """
    errors: list[str] = []

    # Check required
    if value is None or value == "":
        if field.required:
            errors.append(f"Field '{field.name}' is required")
            return None, errors
        else:
            # Return default value
            return field.default, []

    # Type-specific validation
    if field.type == FieldType.STRING:
        validated, errs = _validate_string(field, value)
    elif field.type == FieldType.SECRET:
        validated, errs = _validate_string(field, value)  # Same as string
    elif field.type == FieldType.TEXTAREA:
        validated, errs = _validate_string(field, value)
    elif field.type == FieldType.NUMBER:
        validated, errs = _validate_number(field, value)
    elif field.type == FieldType.INTEGER:
        validated, errs = _validate_integer(field, value)
    elif field.type == FieldType.BOOLEAN:
        validated, errs = _validate_boolean(field, value)
    elif field.type == FieldType.SELECT:
        validated, errs = _validate_select(field, value)
    elif field.type == FieldType.MULTISELECT:
        validated, errs = _validate_multiselect(field, value)
    else:
        # Unknown type, accept as-is
        validated, errs = value, []

    if errs:
        errors.extend(errs)

    return validated, errors


def _validate_string(
    field: ProviderFieldSchema,
    value: Any,
) -> tuple[str | None, list[str]]:
    """Validate string field."""
    errors: list[str] = []

    # Convert to string
    if not isinstance(value, str):
        try:
            value = str(value)
        except Exception:
            errors.append(f"Field '{field.name}' must be a string")
            return None, errors

    # Check min_length
    if field.min_length is not None and len(value) < field.min_length:
        errors.append(
            f"Field '{field.name}' must be at least {field.min_length} characters"
        )

    # Check max_length
    if field.max_length is not None and len(value) > field.max_length:
        errors.append(
            f"Field '{field.name}' must be at most {field.max_length} characters"
        )

    # Check pattern
    if field.pattern is not None:
        if not re.match(field.pattern, value):
            errors.append(f"Field '{field.name}' does not match required pattern")

    return value, errors


def _validate_number(
    field: ProviderFieldSchema,
    value: Any,
) -> tuple[float | None, list[str]]:
    """Validate number (float) field."""
    errors: list[str] = []

    # Convert to float
    if not isinstance(value, (int, float)):
        try:
            value = float(value)
        except (ValueError, TypeError):
            errors.append(f"Field '{field.name}' must be a number")
            return None, errors
    else:
        value = float(value)

    # Check min
    if field.min is not None and value < field.min:
        errors.append(f"Field '{field.name}' must be >= {field.min}")

    # Check max
    if field.max is not None and value > field.max:
        errors.append(f"Field '{field.name}' must be <= {field.max}")

    return value, errors


def _validate_integer(
    field: ProviderFieldSchema,
    value: Any,
) -> tuple[int | None, list[str]]:
    """Validate integer field."""
    errors: list[str] = []

    # Convert to int
    if not isinstance(value, int) or isinstance(value, bool):
        try:
            value = int(value)
        except (ValueError, TypeError):
            errors.append(f"Field '{field.name}' must be an integer")
            return None, errors

    # Check min
    if field.min is not None and value < field.min:
        errors.append(f"Field '{field.name}' must be >= {int(field.min)}")

    # Check max
    if field.max is not None and value > field.max:
        errors.append(f"Field '{field.name}' must be <= {int(field.max)}")

    return value, errors


def _validate_boolean(
    field: ProviderFieldSchema,
    value: Any,
) -> tuple[bool | None, list[str]]:
    """Validate boolean field."""
    errors: list[str] = []

    # Convert to bool
    if isinstance(value, bool):
        return value, []

    if isinstance(value, str):
        if value.lower() in ("true", "1", "yes", "on"):
            return True, []
        elif value.lower() in ("false", "0", "no", "off"):
            return False, []

    if isinstance(value, int):
        return bool(value), []

    errors.append(f"Field '{field.name}' must be a boolean")
    return None, errors


def _validate_select(
    field: ProviderFieldSchema,
    value: Any,
) -> tuple[str | None, list[str]]:
    """Validate select field."""
    errors: list[str] = []

    if not isinstance(value, str):
        try:
            value = str(value)
        except Exception:
            errors.append(f"Field '{field.name}' must be a string")
            return None, errors

    # Check valid options
    if field.options:
        valid_values = [opt.value for opt in field.options]
        if value not in valid_values:
            errors.append(
                f"Field '{field.name}' must be one of: {', '.join(valid_values)}"
            )
            return None, errors

    return value, errors


def _validate_multiselect(
    field: ProviderFieldSchema,
    value: Any,
) -> tuple[list[str] | None, list[str]]:
    """Validate multiselect field."""
    errors: list[str] = []

    # Ensure value is a list
    if not isinstance(value, list):
        if isinstance(value, str):
            value = [value]
        else:
            errors.append(f"Field '{field.name}' must be a list")
            return None, errors

    # Check valid options
    if field.options:
        valid_values = [opt.value for opt in field.options]
        invalid = [v for v in value if v not in valid_values]
        if invalid:
            errors.append(
                f"Field '{field.name}' contains invalid values: {', '.join(invalid)}"
            )
            return None, errors

    return value, errors
