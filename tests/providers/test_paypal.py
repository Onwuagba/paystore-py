"""Tests for the PayPal provider."""

import json

import pytest

from paystore.core.config import Config
from paystore.core.exceptions import ConfigurationError, ProviderError
from paystore.providers.paypal.provider import PaypalProvider, _format_amount


@pytest.fixture
def provider(paypal_config):
    return PaypalProvider(paypal_config)


def test_requires_api_secret():
    config = Config(provider="paypal", api_key="client_id", environment="sandbox")
    with pytest.raises(ConfigurationError, match="api_secret"):
        PaypalProvider(config)


def test_format_amount_converts_minor_units_to_decimal_string():
    assert _format_amount(1000, "USD") == "10.00"
    assert _format_amount(150, "USD") == "1.50"


def test_format_amount_leaves_zero_decimal_currency_as_is():
    assert _format_amount(500, "JPY") == "500"


def _mock_token_response(monkeypatch, provider, token="mock_token", expires_in=3600):
    def fake_post_form(url, data, headers):
        assert url.endswith("/v1/oauth2/token")
        return {"access_token": token, "expires_in": expires_in}

    monkeypatch.setattr(provider.client, "post_form", fake_post_form)


def test_get_access_token_fetches_and_caches(provider, monkeypatch):
    calls = []

    def fake_post_form(url, data, headers):
        calls.append(url)
        return {"access_token": "tok_1", "expires_in": 3600}

    monkeypatch.setattr(provider.client, "post_form", fake_post_form)
    token1 = provider._get_access_token()
    token2 = provider._get_access_token()
    assert token1 == token2 == "tok_1"
    assert len(calls) == 1  # cached on second call


def test_initialize_payment_returns_approval_link(provider, monkeypatch):
    _mock_token_response(monkeypatch, provider)

    def fake_post(url, data, headers):
        assert data["purchase_units"][0]["amount"]["value"] == "10.00"
        return {
            "id": "ORDER_1",
            "status": "CREATED",
            "links": [
                {"rel": "self", "href": "https://api/v2/checkout/orders/ORDER_1"},
                {"rel": "approve", "href": "https://paypal.com/approve/ORDER_1"},
            ],
        }

    monkeypatch.setattr(provider.client, "post", fake_post)
    result = provider.initialize_payment(
        amount=1000, email="a@example.com", currency="USD"
    )
    assert result["reference"] == "ORDER_1"
    assert result["authorization_url"] == "https://paypal.com/approve/ORDER_1"


def test_verify_payment_returns_success_when_already_completed(provider, monkeypatch):
    _mock_token_response(monkeypatch, provider)
    monkeypatch.setattr(
        provider.client,
        "get",
        lambda url, headers: {"id": "ORDER_1", "status": "COMPLETED"},
    )
    result = provider.verify_payment("ORDER_1")
    assert result["status"] == "success"


def test_verify_payment_captures_when_approved(provider, monkeypatch):
    _mock_token_response(monkeypatch, provider)
    monkeypatch.setattr(
        provider.client,
        "get",
        lambda url, headers: {"id": "ORDER_1", "status": "APPROVED"},
    )
    captured = {}

    def fake_post(url, data, headers):
        captured["url"] = url
        return {"id": "ORDER_1", "status": "COMPLETED"}

    monkeypatch.setattr(provider.client, "post", fake_post)
    result = provider.verify_payment("ORDER_1")
    assert result["status"] == "success"
    assert captured["url"].endswith("/capture")


def test_verify_payment_pending_for_created(provider, monkeypatch):
    _mock_token_response(monkeypatch, provider)
    monkeypatch.setattr(
        provider.client,
        "get",
        lambda url, headers: {"id": "ORDER_1", "status": "CREATED"},
    )
    result = provider.verify_payment("ORDER_1")
    assert result["status"] == "pending"


def test_refund_payment_resolves_capture_id(provider, monkeypatch):
    _mock_token_response(monkeypatch, provider)
    monkeypatch.setattr(
        provider.client,
        "get",
        lambda url, headers: {
            "purchase_units": [
                {
                    "amount": {"currency_code": "USD"},
                    "payments": {"captures": [{"id": "CAP_1"}]},
                }
            ]
        },
    )
    captured = {}

    def fake_post(url, data, headers):
        captured["url"] = url
        captured["data"] = data
        return {"id": "REF_1", "status": "COMPLETED"}

    monkeypatch.setattr(provider.client, "post", fake_post)
    result = provider.refund_payment("ORDER_1", amount=500)
    assert result["reference"] == "REF_1"
    assert captured["url"].endswith("/captures/CAP_1/refund")
    assert captured["data"]["amount"]["value"] == "5.00"


def test_refund_payment_raises_when_no_capture(provider, monkeypatch):
    _mock_token_response(monkeypatch, provider)
    monkeypatch.setattr(
        provider.client,
        "get",
        lambda url, headers: {"purchase_units": [{"payments": {"captures": []}}]},
    )
    with pytest.raises(ProviderError, match="no capture to refund"):
        provider.refund_payment("ORDER_1")


def test_charge_authorization_not_implemented(provider):
    with pytest.raises(NotImplementedError):
        provider.charge_authorization(
            authorization_code="x", email="a@example.com", amount=100
        )


def test_verify_webhook_signature_requires_webhook_secret(paypal_config):
    paypal_config.webhook_secret = None
    provider = PaypalProvider(paypal_config)
    with pytest.raises(ConfigurationError):
        provider.verify_webhook_signature(b"{}", json.dumps({"transmission_id": "x"}))


def test_verify_webhook_signature_rejects_malformed_signature(provider):
    assert provider.verify_webhook_signature(b"{}", "not-json") is False


def test_verify_webhook_signature_rejects_malformed_payload(provider):
    assert provider.verify_webhook_signature(b"not-json", json.dumps({})) is False


def test_verify_webhook_signature_valid(provider, monkeypatch):
    _mock_token_response(monkeypatch, provider)
    monkeypatch.setattr(
        provider.client,
        "post",
        lambda url, data, headers: {"verification_status": "SUCCESS"},
    )
    signature = json.dumps(
        {
            "transmission_id": "tid",
            "transmission_time": "2026-01-01T00:00:00Z",
            "cert_url": "https://paypal.com/cert",
            "auth_algo": "SHA256withRSA",
            "transmission_sig": "sig",
        }
    )
    assert provider.verify_webhook_signature(b'{"id": "evt_1"}', signature) is True


def test_verify_webhook_signature_invalid(provider, monkeypatch):
    _mock_token_response(monkeypatch, provider)
    monkeypatch.setattr(
        provider.client,
        "post",
        lambda url, data, headers: {"verification_status": "FAILURE"},
    )
    signature = json.dumps(
        {
            "transmission_id": "tid",
            "transmission_time": "2026-01-01T00:00:00Z",
            "cert_url": "https://paypal.com/cert",
            "auth_algo": "SHA256withRSA",
            "transmission_sig": "bad",
        }
    )
    assert provider.verify_webhook_signature(b'{"id": "evt_1"}', signature) is False
