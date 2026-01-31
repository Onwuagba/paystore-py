"""Pytest configuration."""

import pytest
from paystore.core.config import Config


@pytest.fixture
def mock_config():
    """Mock configuration."""
    return Config(provider="paystack", api_key="sk_test_mock", environment="sandbox")
