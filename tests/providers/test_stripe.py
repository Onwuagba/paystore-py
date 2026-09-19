"""Tests for the Stripe provider."""

import hashlib
import hmac
import time

import pytest

from paystore.core.exceptions import ConfigurationError, ProviderError
from paystore.providers.stripe.provider import StripeProvider, _flatten_params


@pytest.fixture
def provider(stripe_config):
    return StripeProvider(stripe_config)


def test_flatten_params_expands_nested_lists_and_dicts():
    flat = _flatten_params(
        {
            "mode": "payment",
            "line_items": [
                {"price_data": {"currency": "usd", "unit_amount": 1000}, "quantity": 1}
            ],
        }
    )
    assert flat == {
        "mode": "payment",
        "line_items[0][price_data][currency]": "usd",
        "line_items[0][price_data][unit_amount]": 1000,
        "line_items[0][quantity]": 1,
    }


def test_flatten_params_converts_booleans_and_drops_none():
    flat = _flatten_params({"confirm": True, "off_session": False, "customer": None})
    assert flat == {"confirm": "true", "off_session": "false"}


def test_initialize_payment_normalizes_response(provider, monkeypatch):
    monkeypatch.setattr(
        provider.client,
        "post_form",
        lambda url, data, headers: {
            "id": "cs_test_1",
            "url": "https://checkout.stripe.com/pay/cs_test_1",
        },
    )
    result = provider.initialize_payment(
        amount=1000, email="a@example.com", currency="usd"
    )
    assert result["authorization_url"] == "https://checkout.stripe.com/pay/cs_test_1"
    assert result["reference"] == "cs_test_1"


def test_initialize_payment_raises_on_stripe_error(provider, monkeypatch):
    monkeypatch.setattr(
        provider.client,
        "post_form",
        lambda url, data, headers: {"error": {"message": "Invalid API Key"}},
    )
    with pytest.raises(ProviderError, match="Invalid API Key"):
        provider.initialize_payment(amount=1000, email="a@example.com", currency="usd")


def test_verify_payment_normalizes_status(provider, monkeypatch):
    monkeypatch.setattr(
        provider.client,
        "get",
        lambda url, headers: {"id": "cs_test_1", "payment_status": "paid"},
    )
    result = provider.verify_payment("cs_test_1")
    assert result["status"] == "success"


def test_charge_authorization_normalizes_status(provider, monkeypatch):
    monkeypatch.setattr(
        provider.client,
        "post_form",
        lambda url, data, headers: {"id": "pi_1", "status": "succeeded"},
    )
    result = provider.charge_authorization(
        authorization_code="pm_1", email="a@example.com", amount=500, currency="usd"
    )
    assert result["status"] == "success"


def test_create_customer_maps_id_to_customer_code(provider, monkeypatch):
    monkeypatch.setattr(
        provider.client,
        "post_form",
        lambda url, data, headers: {"id": "cus_1", "email": "a@example.com"},
    )
    result = provider.create_customer(email="a@example.com", first_name="Ada")
    assert result["customer_code"] == "cus_1"


def test_list_customer_authorizations_maps_card_fields(provider, monkeypatch):
    monkeypatch.setattr(
        provider.client,
        "get",
        lambda url, headers: {
            "data": [
                {
                    "id": "pm_1",
                    "card": {
                        "brand": "visa",
                        "last4": "4242",
                        "exp_month": 12,
                        "exp_year": 2099,
                    },
                }
            ]
        },
    )
    result = provider.list_customer_authorizations("cus_1")
    assert result[0]["authorization_code"] == "pm_1"
    assert result[0]["last4"] == "4242"
    assert result[0]["reusable"] is True


def test_verify_webhook_signature_valid(provider):
    payload = b'{"type": "checkout.session.completed"}'
    timestamp = str(int(time.time()))
    signed_payload = f"{timestamp}.{payload.decode()}".encode()
    expected_sig = hmac.new(
        provider.config.webhook_secret.encode(), signed_payload, hashlib.sha256
    ).hexdigest()
    header = f"t={timestamp},v1={expected_sig}"
    assert provider.verify_webhook_signature(payload, header) is True


def test_verify_webhook_signature_invalid_hash(provider):
    timestamp = str(int(time.time()))
    header = f"t={timestamp},v1=deadbeef"
    assert provider.verify_webhook_signature(b"payload", header) is False


def test_verify_webhook_signature_requires_webhook_secret(stripe_config):
    stripe_config.webhook_secret = None
    provider = StripeProvider(stripe_config)
    with pytest.raises(ConfigurationError):
        provider.verify_webhook_signature(b"payload", "t=1,v1=abc")
