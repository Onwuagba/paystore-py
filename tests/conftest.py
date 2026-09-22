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


@pytest.fixture
def paypal_config():
    """Mock PayPal configuration."""
    return Config(
        provider="paypal",
        api_key="mock_client_id",
        api_secret="mock_client_secret",
        environment="sandbox",
        webhook_secret="mock_webhook_id",
    )


@pytest.fixture
def momo_config():
    """Mock MTN MoMo configuration."""
    return Config(
        provider="momo",
        api_key="mock_api_user",
        api_secret="mock_api_key",
        environment="sandbox",
        webhook_secret="mock_subscription_key",
    )
