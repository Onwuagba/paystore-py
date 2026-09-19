"""Tests for the Paystack provider."""

import hashlib
import hmac

import pytest

from paystore.core.exceptions import ProviderError
from paystore.providers.paystack.provider import PaystackProvider


@pytest.fixture
def provider(mock_config):
    return PaystackProvider(mock_config)


def test_initialize_payment_returns_data_on_success(provider, monkeypatch):
    monkeypatch.setattr(
        provider.client,
        "post",
        lambda url, data, headers: {
            "status": True,
            "data": {"reference": "TXN_1", "authorization_url": "https://pay.example"},
        },
    )
    result = provider.initialize_payment(amount=1000, email="a@example.com")
    assert result["reference"] == "TXN_1"
    assert result["authorization_url"] == "https://pay.example"


def test_initialize_payment_raises_provider_error_on_failure(provider, monkeypatch):
    monkeypatch.setattr(
        provider.client,
        "post",
        lambda url, data, headers: {"status": False, "message": "Invalid key"},
    )
    with pytest.raises(ProviderError, match="Invalid key"):
        provider.initialize_payment(amount=1000, email="a@example.com")


def test_verify_payment_returns_data_on_success(provider, monkeypatch):
    monkeypatch.setattr(
        provider.client,
        "get",
        lambda url, headers: {"status": True, "data": {"status": "success"}},
    )
    result = provider.verify_payment("TXN_1")
    assert result["status"] == "success"


def test_charge_authorization_success(provider, monkeypatch):
    monkeypatch.setattr(
        provider.client,
        "post",
        lambda url, data, headers: {"status": True, "data": {"status": "success"}},
    )
    result = provider.charge_authorization(
        authorization_code="AUTH_1", email="a@example.com", amount=500
    )
    assert result["status"] == "success"


def test_verify_payment_raises_provider_error_on_failure(provider, monkeypatch):
    monkeypatch.setattr(
        provider.client,
        "get",
        lambda url, headers: {"status": False, "message": "Transaction not found"},
    )
    with pytest.raises(ProviderError, match="Transaction not found"):
        provider.verify_payment("unknown")


def test_charge_authorization_raises_provider_error_on_failure(provider, monkeypatch):
    monkeypatch.setattr(
        provider.client,
        "post",
        lambda url, data, headers: {"status": False, "message": "Card declined"},
    )
    with pytest.raises(ProviderError, match="Card declined"):
        provider.charge_authorization(
            authorization_code="AUTH_1", email="a@example.com", amount=500
        )


def test_create_customer_includes_optional_fields(provider, monkeypatch):
    captured = {}

    def fake_post(url, data, headers):
        captured.update(data)
        return {"status": True, "data": {"customer_code": "CUS_1"}}

    monkeypatch.setattr(provider.client, "post", fake_post)
    result = provider.create_customer(
        email="a@example.com", first_name="Ada", last_name="Lovelace", phone="123"
    )
    assert result["customer_code"] == "CUS_1"
    assert captured["first_name"] == "Ada"
    assert captured["last_name"] == "Lovelace"
    assert captured["phone"] == "123"


def test_get_customer_returns_data(provider, monkeypatch):
    monkeypatch.setattr(
        provider.client,
        "get",
        lambda url, headers: {"status": True, "data": {"customer_code": "CUS_1"}},
    )
    result = provider.get_customer("CUS_1")
    assert result["customer_code"] == "CUS_1"


def test_get_customer_raises_on_not_found(provider, monkeypatch):
    monkeypatch.setattr(
        provider.client,
        "get",
        lambda url, headers: {"status": False, "message": "Customer not found"},
    )
    with pytest.raises(ProviderError, match="Customer not found"):
        provider.get_customer("unknown")


def test_update_customer_returns_data(provider, monkeypatch):
    monkeypatch.setattr(
        provider.client,
        "post",
        lambda url, data, headers: {"status": True, "data": {"phone": "456"}},
    )
    result = provider.update_customer("CUS_1", phone="456")
    assert result["phone"] == "456"


def test_deactivate_authorization_success(provider, monkeypatch):
    monkeypatch.setattr(
        provider.client,
        "post",
        lambda url, data, headers: {"status": True, "message": "Deactivated"},
    )
    result = provider.deactivate_authorization("AUTH_1")
    assert result == {"success": True, "message": "Deactivated"}


def test_deactivate_authorization_raises_on_failure(provider, monkeypatch):
    monkeypatch.setattr(
        provider.client,
        "post",
        lambda url, data, headers: {"status": False, "message": "Not found"},
    )
    with pytest.raises(ProviderError, match="Not found"):
        provider.deactivate_authorization("unknown")


def test_list_customer_authorizations(provider, monkeypatch):
    monkeypatch.setattr(
        provider.client,
        "get",
        lambda url, headers: {
            "status": True,
            "data": {"authorizations": [{"authorization_code": "AUTH_1"}]},
        },
    )
    result = provider.list_customer_authorizations("CUS_1")
    assert result == [{"authorization_code": "AUTH_1"}]


def test_verify_webhook_signature_valid(provider):
    payload = b'{"event": "charge.success"}'
    signature = hmac.new(
        provider.config.api_key.encode(), payload, hashlib.sha512
    ).hexdigest()
    assert provider.verify_webhook_signature(payload, signature) is True


def test_verify_webhook_signature_invalid(provider):
    assert provider.verify_webhook_signature(b"payload", "bad-signature") is False
