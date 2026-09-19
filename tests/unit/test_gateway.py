"""Tests for Gateway class."""

import pytest

from paystore.core.exceptions import ConfigurationError
from paystore.core.gateway import Gateway


def test_gateway_initialization():
    """Test gateway can be initialized."""
    gateway = Gateway(provider="paystack", api_key="sk_test_key")
    assert gateway is not None


def test_gateway_invalid_provider():
    """Test gateway raises error for invalid provider."""
    with pytest.raises(ConfigurationError):
        Gateway(provider="invalid_provider", api_key="sk_test_key")
