"""Tests for the Paystack provider."""

import hashlib
import hmac

import pytest

from paystore.core.exceptions import AuthenticationError, ProviderError
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


def test_initialize_payment_passes_through_specific_exception_type(
    provider, monkeypatch
):
    def raise_auth_error(url, data, headers):
        raise AuthenticationError("bad key")

    monkeypatch.setattr(provider.client, "post", raise_auth_error)
    with pytest.raises(AuthenticationError):
        provider.initialize_payment(amount=1000, email="a@example.com")


def test_refund_payment_full(provider, monkeypatch):
    captured = {}

    def fake_post(url, data, headers):
        captured.update(data)
        return {"status": True, "data": {"status": "processing"}}

    monkeypatch.setattr(provider.client, "post", fake_post)
    result = provider.refund_payment("TXN_1")
    assert result["status"] == "processing"
    assert captured == {"transaction": "TXN_1"}


def test_refund_payment_partial_includes_amount(provider, monkeypatch):
    captured = {}

    def fake_post(url, data, headers):
        captured.update(data)
        return {"status": True, "data": {"status": "processing"}}

    monkeypatch.setattr(provider.client, "post", fake_post)
    provider.refund_payment("TXN_1", amount=500)
    assert captured == {"transaction": "TXN_1", "amount": 500}


def test_refund_payment_raises_on_failure(provider, monkeypatch):
    monkeypatch.setattr(
        provider.client,
        "post",
        lambda url, data, headers: {"status": False, "message": "Already refunded"},
    )
    with pytest.raises(ProviderError, match="Already refunded"):
        provider.refund_payment("TXN_1")


def test_create_plan_success(provider, monkeypatch):
    monkeypatch.setattr(
        provider.client,
        "post",
        lambda url, data, headers: {"status": True, "data": {"plan_code": "PLN_1"}},
    )
    result = provider.create_plan(name="Monthly", amount=5000, interval="monthly")
    assert result["plan_code"] == "PLN_1"


def test_create_subscription_success(provider, monkeypatch):
    monkeypatch.setattr(
        provider.client,
        "post",
        lambda url, data, headers: {
            "status": True,
            "data": {"subscription_code": "SUB_1"},
        },
    )
    result = provider.create_subscription(customer="CUS_1", plan="PLN_1")
    assert result["subscription_code"] == "SUB_1"


def test_cancel_subscription_success(provider, monkeypatch):
    def fake_get(url, headers):
        return {"status": True, "data": {"email_token": "tok_abc"}}

    captured = {}

    def fake_post(url, data, headers):
        captured.update(data)
        return {"status": True, "message": "Subscription disabled"}

    monkeypatch.setattr(provider.client, "get", fake_get)
    monkeypatch.setattr(provider.client, "post", fake_post)

    result = provider.cancel_subscription("SUB_1")
    assert result == {"success": True, "message": "Subscription disabled"}
    assert captured == {"code": "SUB_1", "token": "tok_abc"}


def test_cancel_subscription_raises_when_not_found(provider, monkeypatch):
    monkeypatch.setattr(
        provider.client,
        "get",
        lambda url, headers: {"status": False, "message": "Subscription not found"},
    )
    with pytest.raises(ProviderError, match="Subscription not found"):
        provider.cancel_subscription("unknown")


def test_create_transfer_recipient_success(provider, monkeypatch):
    captured = {}

    def fake_post(url, data, headers):
        captured.update(data)
        return {"status": True, "data": {"recipient_code": "RCP_1"}}

    monkeypatch.setattr(provider.client, "post", fake_post)
    result = provider.create_transfer_recipient(
        name="Ada Lovelace", account_number="0123456789", bank_code="058"
    )
    assert result["recipient_code"] == "RCP_1"
    assert captured["type"] == "nuban"
    assert captured["account_number"] == "0123456789"


def test_create_transfer_recipient_raises_on_failure(provider, monkeypatch):
    monkeypatch.setattr(
        provider.client,
        "post",
        lambda url, data, headers: {"status": False, "message": "Invalid bank code"},
    )
    with pytest.raises(ProviderError, match="Invalid bank code"):
        provider.create_transfer_recipient(
            name="Ada", account_number="0123456789", bank_code="000"
        )


def test_initiate_transfer_success(provider, monkeypatch):
    captured = {}

    def fake_post(url, data, headers):
        captured.update(data)
        return {"status": True, "data": {"transfer_code": "TRF_1", "status": "pending"}}

    monkeypatch.setattr(provider.client, "post", fake_post)
    result = provider.initiate_transfer(recipient="RCP_1", amount=5000, reason="Payout")
    assert result["transfer_code"] == "TRF_1"
    assert captured["recipient"] == "RCP_1"
    assert captured["amount"] == 5000
    assert captured["source"] == "balance"


def test_initiate_transfer_raises_on_failure(provider, monkeypatch):
    monkeypatch.setattr(
        provider.client,
        "post",
        lambda url, data, headers: {"status": False, "message": "Insufficient balance"},
    )
    with pytest.raises(ProviderError, match="Insufficient balance"):
        provider.initiate_transfer(recipient="RCP_1", amount=5000)


def test_create_subaccount_success(provider, monkeypatch):
    captured = {}

    def fake_post(url, data, headers):
        captured.update(data)
        return {"status": True, "data": {"subaccount_code": "ACCT_1"}}

    monkeypatch.setattr(provider.client, "post", fake_post)
    result = provider.create_subaccount(
        business_name="Shop", account_number="0123456789", bank_code="058"
    )
    assert result["subaccount_code"] == "ACCT_1"
    assert captured["settlement_bank"] == "058"
    assert captured["percentage_charge"] == 0


def test_create_subaccount_raises_on_failure(provider, monkeypatch):
    monkeypatch.setattr(
        provider.client,
        "post",
        lambda url, data, headers: {"status": False, "message": "Invalid bank"},
    )
    with pytest.raises(ProviderError, match="Invalid bank"):
        provider.create_subaccount(
            business_name="Shop", account_number="0123456789", bank_code="000"
        )


def test_verify_webhook_signature_valid(provider):
    payload = b'{"event": "charge.success"}'
    signature = hmac.new(
        provider.config.api_key.encode(), payload, hashlib.sha512
    ).hexdigest()
    assert provider.verify_webhook_signature(payload, signature) is True


def test_verify_webhook_signature_invalid(provider):
    assert provider.verify_webhook_signature(b"payload", "bad-signature") is False
