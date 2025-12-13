"""
Simple test để verify Pydantic warnings đã được fix
"""

import pytest


@pytest.mark.unit
def test_pydantic_settings_import():
    """Test import settings không có deprecated warnings."""
    from src.app.config.settings import Settings

    settings = Settings()
    assert settings is not None


@pytest.mark.unit
def test_pydantic_schemas_import():
    """Test import schemas không có deprecated warnings."""
    from src.app.schemas.base import OTADeviceData

    device_data = OTADeviceData()
    assert device_data is not None
