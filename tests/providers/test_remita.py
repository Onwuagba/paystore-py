"""Tests for the Remita provider."""

import hashlib

import pytest

from paystore.core.config import Config
from paystore.core.exceptions import (
    AuthenticationError,
    ConfigurationError,
    ProviderError,
)
from paystore.providers.remita.provider import RemitaProvider


@pytest.fixture
def remita_config():
    return Config(
        provider="remita",
        api_key="test_api_key",
        api_secret="test_api_secret",
        merchant_id="MERCHANT_1",
        service_type_id="SERVICE_1",
        environment="sandbox",
    )


@pytest.fixture
def provider(remita_config):
    return RemitaProvider(remita_config)


def test_requires_merchant_credentials():
    config = Config(provider="remita", api_key="test_api_key", environment="sandbox")
    with pytest.raises(ConfigurationError, match="merchant_id"):
        RemitaProvider(config)


def test_initialize_payment_returns_rrr_and_authorization_url(provider, monkeypatch):
    monkeypatch.setattr(
        provider.client,
        "post",
        lambda url, data, headers: {
            "statuscode": "025",
            "RRR": "290000000000",
            "status": "RRR Assigned Successfully",
        },
    )
    result = provider.initialize_payment(amount=1000, email="a@example.com")
    assert result["rrr"] == "290000000000"
    assert result["authorization_url"].endswith("290000000000/pay")


def test_initialize_payment_raises_when_no_rrr(provider, monkeypatch):
    monkeypatch.setattr(
        provider.client,
        "post",
        lambda url, data, headers: {"status": "Invalid credentials"},
    )
    with pytest.raises(ProviderError, match="Invalid credentials"):
        provider.initialize_payment(amount=1000, email="a@example.com")


def test_verify_payment_success_status(provider, monkeypatch):
    monkeypatch.setattr(
        provider.client,
        "get",
        lambda url, headers: {"status": "00", "amount": "1000"},
    )
    result = provider.verify_payment("290000000000")
    assert result["status"] == "success"


def test_verify_payment_failed_status(provider, monkeypatch):
    monkeypatch.setattr(
        provider.client,
        "get",
        lambda url, headers: {"status": "021"},
    )
    result = provider.verify_payment("290000000000")
    assert result["status"] == "failed"


def test_verify_payment_passes_through_specific_exception_type(provider, monkeypatch):
    def raise_auth_error(url, headers):
        raise AuthenticationError("bad key")

    monkeypatch.setattr(provider.client, "get", raise_auth_error)
    with pytest.raises(AuthenticationError):
        provider.verify_payment("290000000000")


def test_charge_authorization_not_implemented(provider):
    with pytest.raises(NotImplementedError):
        provider.charge_authorization(
            authorization_code="x", email="a@example.com", amount=100
        )


def test_verify_webhook_signature_valid(provider):
    payload = b"290000000000|1000|order_1"
    signature = hashlib.sha512(payload + b"test_api_secret").hexdigest()
    assert provider.verify_webhook_signature(payload, signature) is True


def test_verify_webhook_signature_invalid(provider):
    assert provider.verify_webhook_signature(b"payload", "bad-signature") is False


def test_create_customer_not_implemented(provider):
    with pytest.raises(NotImplementedError):
        provider.create_customer(email="a@example.com")
