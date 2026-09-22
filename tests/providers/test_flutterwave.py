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


def test_refund_payment_resolves_id_then_refunds(provider, monkeypatch):
    monkeypatch.setattr(
        provider.client,
        "get",
        lambda url, headers: {
            "status": "success",
            "data": {"id": 998877, "tx_ref": "TXN_1", "status": "successful"},
        },
    )
    captured = {}

    def fake_post(url, data, headers):
        captured["url"] = url
        captured["data"] = data
        return {"status": "success", "data": {"status": "completed"}}

    monkeypatch.setattr(provider.client, "post", fake_post)
    result = provider.refund_payment("TXN_1")
    assert result["status"] == "completed"
    assert captured["url"].endswith("/transactions/998877/refund")
    assert captured["data"] == {}


def test_refund_payment_partial_includes_amount(provider, monkeypatch):
    monkeypatch.setattr(
        provider.client,
        "get",
        lambda url, headers: {"status": "success", "data": {"id": 998877}},
    )
    captured = {}

    def fake_post(url, data, headers):
        captured.update(data)
        return {"status": "success", "data": {}}

    monkeypatch.setattr(provider.client, "post", fake_post)
    provider.refund_payment("TXN_1", amount=200)
    assert captured == {"amount": 200}


def test_refund_payment_raises_when_id_missing(provider, monkeypatch):
    monkeypatch.setattr(
        provider.client,
        "get",
        lambda url, headers: {"status": "success", "data": {}},
    )
    with pytest.raises(ProviderError, match="Could not resolve transaction id"):
        provider.refund_payment("TXN_1")


def test_create_plan_not_implemented(provider):
    with pytest.raises(NotImplementedError):
        provider.create_plan(name="Monthly", amount=5000, interval="monthly")


def test_create_transfer_recipient_not_implemented(provider):
    with pytest.raises(NotImplementedError):
        provider.create_transfer_recipient(
            name="Ada", account_number="0123456789", bank_code="058"
        )


def test_initiate_transfer_success(provider, monkeypatch):
    captured = {}

    def fake_post(url, data, headers):
        captured.update(data)
        return {
            "status": "success",
            "data": {"id": 123, "reference": "gen_ref", "status": "NEW"},
        }

    monkeypatch.setattr(provider.client, "post", fake_post)
    result = provider.initiate_transfer(
        recipient={"account_bank": "058", "account_number": "0123456789"},
        amount=5000,
        reason="Payout",
    )
    assert result["reference"] == "gen_ref"
    assert captured["account_bank"] == "058"
    assert captured["narration"] == "Payout"


def test_initiate_transfer_raises_on_failure(provider, monkeypatch):
    monkeypatch.setattr(
        provider.client,
        "post",
        lambda url, data, headers: {"status": "error", "message": "Invalid account"},
    )
    with pytest.raises(ProviderError, match="Invalid account"):
        provider.initiate_transfer(
            recipient={"account_bank": "058", "account_number": "bad"}, amount=5000
        )
