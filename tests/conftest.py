"""Pytest configuration."""

import pytest

from paystore.core.config import Config


@pytest.fixture
def mock_config():
    """Mock configuration."""
    return Config(provider="paystack", api_key="sk_test_mock", environment="sandbox")


@pytest.fixture
def flutterwave_config():
    """Mock Flutterwave configuration."""
    return Config(
        provider="flutterwave",
        api_key="FLWSECK_TEST-mock",
        environment="sandbox",
        webhook_secret="mock-hash",
    )


@pytest.fixture
def stripe_config():
    """Mock Stripe configuration."""
    return Config(
        provider="stripe",
        api_key="sk_test_mock",
        environment="sandbox",
        webhook_secret="whsec_mock",
    )
