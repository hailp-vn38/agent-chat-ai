"""
Unit tests for Tool Schema Registry.
"""

import pytest

from app.ai.providers.tools.tool_schema_registry import (
    ToolFieldType,
    ToolCategory,
    ToolFieldSchema,
    ToolSchema,
    get_tool_schema,
    get_all_tool_schemas,
    get_tool_schemas_by_category,
    get_all_categories,
    register_tool_schema,
    TOOL_SCHEMAS,
)


class TestToolFieldType:
    """Test ToolFieldType enum."""

    def test_field_types_exist(self):
        """Test all expected field types exist."""
        assert ToolFieldType.STRING.value == "string"
        assert ToolFieldType.SECRET.value == "secret"
        assert ToolFieldType.NUMBER.value == "number"
        assert ToolFieldType.BOOLEAN.value == "boolean"
        assert ToolFieldType.SELECT.value == "select"
        assert ToolFieldType.ARRAY.value == "array"
        assert ToolFieldType.PATH.value == "path"
        assert ToolFieldType.URL.value == "url"


class TestToolCategory:
    """Test ToolCategory enum."""

    def test_categories_exist(self):
        """Test all expected categories exist."""
        assert ToolCategory.WEATHER.value == "weather"
        assert ToolCategory.MUSIC.value == "music"
        assert ToolCategory.REMINDER.value == "reminder"
        assert ToolCategory.NEWS.value == "news"
        assert ToolCategory.AGENT.value == "agent"
        assert ToolCategory.IOT.value == "iot"
        assert ToolCategory.CALENDAR.value == "calendar"
        assert ToolCategory.OTHER.value == "other"


class TestToolFieldSchema:
    """Test ToolFieldSchema dataclass."""

    def test_create_basic_field(self):
        """Test creating a basic field schema."""
        field = ToolFieldSchema(
            name="api_key",
            display_name="API Key",
            field_type=ToolFieldType.SECRET,
            description="Your API key",
            required=True,
        )

        assert field.name == "api_key"
        assert field.display_name == "API Key"
        assert field.field_type == ToolFieldType.SECRET
        assert field.required is True
        assert field.default is None

    def test_create_field_with_options(self):
        """Test creating a field with select options."""
        field = ToolFieldSchema(
            name="source",
            display_name="News Source",
            field_type=ToolFieldType.SELECT,
            options=["vnexpress", "tuoitre"],
            default="vnexpress",
        )

        assert field.options == ["vnexpress", "tuoitre"]
        assert field.default == "vnexpress"

    def test_create_field_with_validation(self):
        """Test creating a field with validation rules."""
        field = ToolFieldSchema(
            name="max_articles",
            display_name="Max Articles",
            field_type=ToolFieldType.NUMBER,
            validation={"min": 1, "max": 50},
            default=10,
        )

        assert field.validation == {"min": 1, "max": 50}


class TestToolSchema:
    """Test ToolSchema dataclass."""

    def test_create_tool_schema(self):
        """Test creating a tool schema."""
        schema = ToolSchema(
            name="test_tool",
            display_name="Test Tool",
            description="A test tool",
            category=ToolCategory.OTHER,
            requires_config=True,
            fields=[
                ToolFieldSchema(
                    name="param1",
                    display_name="Parameter 1",
                    field_type=ToolFieldType.STRING,
                )
            ],
        )

        assert schema.name == "test_tool"
        assert schema.category == ToolCategory.OTHER
        assert len(schema.fields) == 1

    def test_to_dict(self):
        """Test converting tool schema to dict."""
        schema = ToolSchema(
            name="test_tool",
            display_name="Test Tool",
            description="A test tool",
            category=ToolCategory.OTHER,
            requires_config=False,
        )

        result = schema.to_dict()

        assert result["name"] == "test_tool"
        assert result["category"] == "other"
        assert result["requires_config"] is False
        assert result["fields"] == []

    def test_to_dict_with_fields(self):
        """Test converting tool schema with fields to dict."""
        schema = ToolSchema(
            name="test_tool",
            display_name="Test Tool",
            description="A test tool",
            category=ToolCategory.WEATHER,
            requires_config=True,
            fields=[
                ToolFieldSchema(
                    name="api_key",
                    display_name="API Key",
                    field_type=ToolFieldType.SECRET,
                    required=True,
                )
            ],
        )

        result = schema.to_dict()

        assert len(result["fields"]) == 1
        assert result["fields"][0]["name"] == "api_key"
        assert result["fields"][0]["field_type"] == "secret"
        assert result["fields"][0]["required"] is True


class TestToolSchemaRegistry:
    """Test Tool Schema Registry functions."""

    def test_get_weather_schema(self):
        """Test get_weather schema is registered."""
        schema = get_tool_schema("get_weather")

        assert schema is not None
        assert schema.name == "get_weather"
        assert schema.category == ToolCategory.WEATHER
        assert schema.requires_config is True

        # Check expected fields
        field_names = [f.name for f in schema.fields]
        assert "api_key" in field_names
        assert "default_location" in field_names

    def test_get_play_music_schema(self):
        """Test play_music schema is registered."""
        schema = get_tool_schema("play_music")

        assert schema is not None
        assert schema.name == "play_music"
        assert schema.category == ToolCategory.MUSIC

        field_names = [f.name for f in schema.fields]
        assert "music_dir" in field_names
        assert "music_ext" in field_names

    def test_get_reminder_tools_no_config(self):
        """Test reminder tools don't require config."""
        for tool_name in ["create_reminder", "get_list_reminder", "delete_reminder"]:
            schema = get_tool_schema(tool_name)
            assert schema is not None
            assert schema.requires_config is False
            assert len(schema.fields) == 0

    def test_get_nonexistent_schema(self):
        """Test getting schema for non-existent tool."""
        schema = get_tool_schema("nonexistent_tool")
        assert schema is None

    def test_get_all_tool_schemas(self):
        """Test getting all tool schemas."""
        schemas = get_all_tool_schemas()

        assert isinstance(schemas, dict)
        assert len(schemas) > 0
        assert "get_weather" in schemas
        assert "play_music" in schemas
        assert "create_reminder" in schemas

    def test_get_all_categories(self):
        """Test getting all categories."""
        categories = get_all_categories()

        assert isinstance(categories, list)
        assert len(categories) > 0
        assert "weather" in categories
        assert "reminder" in categories

    def test_get_tool_schemas_by_category(self):
        """Test getting schemas by category."""
        reminder_schemas = get_tool_schemas_by_category(ToolCategory.REMINDER)

        assert len(reminder_schemas) > 0
        for schema in reminder_schemas:
            assert schema.category == ToolCategory.REMINDER

    def test_register_tool_schema(self):
        """Test registering a new tool schema."""
        test_schema = ToolSchema(
            name="test_custom_tool",
            display_name="Test Custom Tool",
            description="A custom tool for testing",
            category=ToolCategory.OTHER,
            requires_config=False,
        )

        registered = register_tool_schema(test_schema)

        assert registered == test_schema
        assert "test_custom_tool" in TOOL_SCHEMAS

        # Cleanup
        del TOOL_SCHEMAS["test_custom_tool"]
