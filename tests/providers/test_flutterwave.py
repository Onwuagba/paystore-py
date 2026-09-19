"""Tests for the Flutterwave provider."""

import pytest

from paystore.core.exceptions import ConfigurationError, ProviderError
from paystore.providers.flutterwave.provider import FlutterwaveProvider


@pytest.fixture
def provider(flutterwave_config):
    return FlutterwaveProvider(flutterwave_config)


def test_initialize_payment_normalizes_response(provider, monkeypatch):
    monkeypatch.setattr(
        provider.client,
        "post",
        lambda url, data, headers: {
            "status": "success",
            "data": {"link": "https://checkout.flutterwave.com/pay/abc"},
        },
    )
    result = provider.initialize_payment(amount=1000, email="a@example.com")
    assert result["authorization_url"] == "https://checkout.flutterwave.com/pay/abc"
    assert result["reference"]


def test_initialize_payment_raises_on_failure(provider, monkeypatch):
    monkeypatch.setattr(
        provider.client,
        "post",
        lambda url, data, headers: {"status": "error", "message": "Invalid key"},
    )
    with pytest.raises(ProviderError, match="Invalid key"):
        provider.initialize_payment(amount=1000, email="a@example.com")


def test_verify_payment_normalizes_status(provider, monkeypatch):
    monkeypatch.setattr(
        provider.client,
        "get",
        lambda url, headers: {
            "status": "success",
            "data": {"tx_ref": "TXN_1", "status": "successful"},
        },
    )
    result = provider.verify_payment("TXN_1")
    assert result["status"] == "success"
    assert result["reference"] == "TXN_1"


def test_charge_authorization_normalizes_status(provider, monkeypatch):
    monkeypatch.setattr(
        provider.client,
        "post",
        lambda url, data, headers: {
            "status": "success",
            "data": {"tx_ref": "TXN_2", "status": "successful"},
        },
    )
    result = provider.charge_authorization(
        authorization_code="TOKEN_1", email="a@example.com", amount=500
    )
    assert result["status"] == "success"


def test_verify_webhook_signature_matches_secret_hash(provider):
    assert provider.verify_webhook_signature(b"anything", "mock-hash") is True
    assert provider.verify_webhook_signature(b"anything", "wrong-hash") is False


def test_verify_webhook_signature_requires_webhook_secret(flutterwave_config):
    flutterwave_config.webhook_secret = None
    provider = FlutterwaveProvider(flutterwave_config)
    with pytest.raises(ConfigurationError):
        provider.verify_webhook_signature(b"anything", "some-hash")


def test_create_customer_not_implemented(provider):
    with pytest.raises(NotImplementedError):
        provider.create_customer(email="a@example.com")
