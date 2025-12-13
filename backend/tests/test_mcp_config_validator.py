"""
Tests for MCP configuration validation services.
"""

import pytest

from src.app.schemas.server_mcp_config import ServerMCPConfigCreate
from src.app.services.mcp_config_validator import MCPConfigValidator


def test_validate_name_valid():
    """Test valid name format."""
    MCPConfigValidator.validate_name("valid_name")
    MCPConfigValidator.validate_name("test_123")
    MCPConfigValidator.validate_name("mcp_server_1")


def test_validate_name_invalid():
    """Test invalid name formats."""
    # Too short
    with pytest.raises(ValueError):
        MCPConfigValidator.validate_name("ab")

    # Uppercase
    with pytest.raises(ValueError):
        MCPConfigValidator.validate_name("InvalidName")

    # Spaces
    with pytest.raises(ValueError):
        MCPConfigValidator.validate_name("invalid name")

    # Special characters
    with pytest.raises(ValueError):
        MCPConfigValidator.validate_name("invalid-name")


def test_validate_command_valid():
    """Test valid commands."""
    MCPConfigValidator.validate_command("npx")
    MCPConfigValidator.validate_command("node")
    MCPConfigValidator.validate_command("python")
    MCPConfigValidator.validate_command("python3")
    MCPConfigValidator.validate_command("docker")


def test_validate_command_invalid():
    """Test invalid commands."""
    with pytest.raises(ValueError):
        MCPConfigValidator.validate_command("bash")

    with pytest.raises(ValueError):
        MCPConfigValidator.validate_command("rm")


def test_validate_args_valid():
    """Test valid arguments."""
    MCPConfigValidator.validate_args(["server", "--port", "3000"])
    MCPConfigValidator.validate_args(None)
    MCPConfigValidator.validate_args([])


def test_validate_args_invalid():
    """Test invalid arguments with shell metacharacters."""
    with pytest.raises(ValueError):
        MCPConfigValidator.validate_args(["server; rm -rf /"])

    with pytest.raises(ValueError):
        MCPConfigValidator.validate_args(["$(whoami)"])

    with pytest.raises(ValueError):
        MCPConfigValidator.validate_args(["`id`"])


def test_validate_url_valid():
    """Test valid URLs."""
    MCPConfigValidator.validate_url("http://localhost:3000")
    MCPConfigValidator.validate_url("https://example.com/mcp")
    MCPConfigValidator.validate_url(None)


def test_validate_url_invalid():
    """Test invalid URLs."""
    with pytest.raises(ValueError):
        MCPConfigValidator.validate_url("localhost:3000")  # Missing scheme

    with pytest.raises(ValueError):
        MCPConfigValidator.validate_url("ftp://example.com")  # Invalid scheme


def test_validate_config_stdio_valid():
    """Test valid stdio config."""
    config = ServerMCPConfigCreate(
        name="test_stdio",
        type="stdio",
        command="npx",
        args=["mcp-server"],
    )
    MCPConfigValidator.validate_config(config)


def test_validate_config_stdio_missing_command():
    """Test stdio config missing command."""
    config = ServerMCPConfigCreate(
        name="test_stdio",
        type="stdio",
        command=None,  # Missing
    )
    with pytest.raises(ValueError):
        MCPConfigValidator.validate_config(config)


def test_validate_config_http_valid():
    """Test valid HTTP config."""
    config = ServerMCPConfigCreate(
        name="test_http",
        type="http",
        url="http://localhost:3000",
        headers={"Authorization": "Bearer token"},
    )
    MCPConfigValidator.validate_config(config)


def test_validate_config_http_missing_url():
    """Test HTTP config missing URL."""
    config = ServerMCPConfigCreate(
        name="test_http",
        type="http",
        url=None,  # Missing
    )
    with pytest.raises(ValueError):
        MCPConfigValidator.validate_config(config)
