"""Tests for the MTN MoMo provider."""

import pytest

from paystore.core.config import Config
from paystore.core.exceptions import ConfigurationError, ProviderError
from paystore.providers.momo.provider import MomoProvider


@pytest.fixture
def provider(momo_config):
    return MomoProvider(momo_config)


def test_requires_api_secret_and_webhook_secret():
    config = Config(provider="momo", api_key="api_user", environment="sandbox")
    with pytest.raises(ConfigurationError, match="api_secret"):
        MomoProvider(config)


def test_requires_webhook_secret_specifically():
    config = Config(
        provider="momo",
        api_key="api_user",
        api_secret="api_key_secret",
        environment="sandbox",
    )
    with pytest.raises(ConfigurationError, match="webhook_secret"):
        MomoProvider(config)


def test_target_environment_defaults_to_sandbox(provider):
    assert provider.target_environment == "sandbox"


def test_target_environment_uses_merchant_id_when_set(momo_config):
    momo_config.merchant_id = "mtnuganda"
    provider = MomoProvider(momo_config)
    assert provider.target_environment == "mtnuganda"


def _mock_token_response(monkeypatch, provider, token="mock_token", expires_in=3600):
    def fake_post(url, data, headers):
        assert url.endswith("/collection/token/")
        assert "Ocp-Apim-Subscription-Key" in headers
        return {"access_token": token, "expires_in": expires_in}

    monkeypatch.setattr(provider.client, "post", fake_post)


def test_get_access_token_fetches_and_caches(provider, monkeypatch):
    calls = []

    def fake_post(url, data, headers):
        calls.append(url)
        return {"access_token": "tok_1", "expires_in": 3600}

    monkeypatch.setattr(provider.client, "post", fake_post)
    token1 = provider._get_access_token()
    token2 = provider._get_access_token()
    assert token1 == token2 == "tok_1"
    assert len(calls) == 1


def test_initialize_payment_requires_phone(provider):
    with pytest.raises(ProviderError, match="phone"):
        provider.initialize_payment(amount=1000, email="a@example.com")


def test_initialize_payment_sends_request_to_pay(provider, monkeypatch):
    _mock_token_response(monkeypatch, provider)
    captured = {}

    def fake_post(url, data, headers):
        if url.endswith("/requesttopay"):
            captured["url"] = url
            captured["data"] = data
            captured["headers"] = headers
            return {}
        return {"access_token": "tok_1", "expires_in": 3600}

    monkeypatch.setattr(provider.client, "post", fake_post)
    result = provider.initialize_payment(
        amount=1000, email="a@example.com", currency="EUR", phone="256781234567"
    )
    assert result["status"] == "pending"
    assert result["authorization_url"] is None
    assert captured["data"]["amount"] == "10.00"
    assert captured["data"]["payer"] == {
        "partyIdType": "MSISDN",
        "partyId": "256781234567",
    }
    assert captured["headers"]["X-Reference-Id"] == result["reference"]
    assert captured["headers"]["X-Target-Environment"] == "sandbox"


def test_verify_payment_maps_successful_status(provider, monkeypatch):
    _mock_token_response(monkeypatch, provider)
    monkeypatch.setattr(
        provider.client,
        "get",
        lambda url, headers: {"status": "SUCCESSFUL", "amount": "10.00"},
    )
    result = provider.verify_payment("TXN_1")
    assert result["status"] == "success"


def test_verify_payment_maps_pending_status(provider, monkeypatch):
    _mock_token_response(monkeypatch, provider)
    monkeypatch.setattr(
        provider.client, "get", lambda url, headers: {"status": "PENDING"}
    )
    result = provider.verify_payment("TXN_1")
    assert result["status"] == "pending"


def test_verify_payment_maps_failed_status(provider, monkeypatch):
    _mock_token_response(monkeypatch, provider)
    monkeypatch.setattr(
        provider.client, "get", lambda url, headers: {"status": "FAILED"}
    )
    result = provider.verify_payment("TXN_1")
    assert result["status"] == "failed"


def test_charge_authorization_not_implemented(provider):
    with pytest.raises(NotImplementedError):
        provider.charge_authorization(
            authorization_code="x", email="a@example.com", amount=100
        )


def test_verify_webhook_signature_not_implemented(provider):
    with pytest.raises(NotImplementedError):
        provider.verify_webhook_signature(b"{}", "signature")


def test_create_customer_not_implemented(provider):
    with pytest.raises(NotImplementedError):
        provider.create_customer(email="a@example.com")
