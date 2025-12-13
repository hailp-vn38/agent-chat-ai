"""
Test helpers và utilities cho testing
"""

from typing import Dict, Any
from faker import Faker

fake = Faker()


def create_user_payload(**kwargs) -> Dict[str, Any]:
    """Tạo user payload cho testing."""
    default_payload = {
        "name": fake.name(),
        "email": fake.email(),
        "password": "TestPassword123!",
    }
    default_payload.update(kwargs)
    return default_payload


def create_agent_payload(**kwargs) -> Dict[str, Any]:
    """Tạo agent payload cho testing."""
    default_payload = {
        "agent_name": f"Test Agent {fake.word()}",
        "description": fake.text(max_nb_chars=200),
        "status": 1,
    }
    default_payload.update(kwargs)
    return default_payload


def create_device_payload(**kwargs) -> Dict[str, Any]:
    """Tạo device payload cho testing."""
    default_payload = {
        "device_name": f"Test Device {fake.word()}",
        "device_type": "speaker",
        "location": fake.city(),
    }
    default_payload.update(kwargs)
    return default_payload


def assert_response_success(response, status_code: int = 200):
    """Assert response thành công."""
    assert (
        response.status_code == status_code
    ), f"Expected {status_code}, got {response.status_code}: {response.text}"
    data = response.json()
    assert data.get("success") is True or data.get("data") is not None
    return data


def assert_response_error(response, status_code: int = 400):
    """Assert response lỗi."""
    assert (
        response.status_code == status_code
    ), f"Expected {status_code}, got {response.status_code}"
    data = response.json()
    assert "detail" in data or "message" in data
    return data
