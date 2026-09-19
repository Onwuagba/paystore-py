"""Tests for Gateway class."""

import pytest

from paystore.core.exceptions import ConfigurationError, PaymentError, ValidationError
from paystore.core.gateway import Gateway
from paystore.providers.flutterwave.provider import FlutterwaveProvider
from paystore.providers.paystack.provider import PaystackProvider
from paystore.providers.remita.provider import RemitaProvider
from paystore.providers.stripe.provider import StripeProvider
from paystore.storage.base import BaseStorage


def test_gateway_initialization():
    """Test gateway can be initialized."""
    gateway = Gateway(provider="paystack", api_key="sk_test_key")
    assert gateway is not None


def test_gateway_invalid_provider():
    """Test gateway raises error for invalid provider."""
    with pytest.raises(ConfigurationError):
        Gateway(provider="invalid_provider", api_key="sk_test_key")


def test_gateway_requires_api_key(monkeypatch):
    """Test gateway raises error when no api key can be resolved."""
    for var in ("PAYSTACK_SECRET_KEY", "PAYSTACK_API_KEY", "PAYMENT_API_KEY"):
        monkeypatch.delenv(var, raising=False)
    with pytest.raises(ConfigurationError):
        Gateway(provider="paystack")


@pytest.mark.parametrize(
    "provider,expected_class",
    [
        ("paystack", PaystackProvider),
        ("flutterwave", FlutterwaveProvider),
        ("stripe", StripeProvider),
    ],
)
def test_gateway_loads_each_supported_provider(provider, expected_class):
    """Switching the provider name is enough to swap gateways."""
    gateway = Gateway(provider=provider, api_key="test_key")
    assert isinstance(gateway._provider, expected_class)


def test_gateway_resolves_provider_specific_env_key(monkeypatch):
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_from_env")
    gateway = Gateway(provider="stripe")
    assert gateway.config.api_key == "sk_test_from_env"


def test_gateway_loads_remita_with_extra_credentials():
    gateway = Gateway(
        provider="remita",
        api_key="test_key",
        api_secret="test_secret",
        merchant_id="MERCHANT_1",
        service_type_id="SERVICE_1",
    )
    assert isinstance(gateway._provider, RemitaProvider)


class _FakeProvider:
    """Records calls made through Gateway's operation facades."""

    def __init__(self, config=None):
        self.calls = []

    def initialize_payment(self, **kwargs):
        self.calls.append(("initialize_payment", kwargs))
        return {"reference": "TXN_1"}

    def verify_payment(self, reference):
        self.calls.append(("verify_payment", reference))
        return {"status": "success"}

    def charge_authorization(self, **kwargs):
        self.calls.append(("charge_authorization", kwargs))
        return {"status": "success"}

    def create_customer(self, **kwargs):
        self.calls.append(("create_customer", kwargs))
        return {"customer_code": "CUS_1"}

    def get_customer(self, customer_code):
        self.calls.append(("get_customer", customer_code))
        return {"customer_code": customer_code}

    def update_customer(self, customer_code, **kwargs):
        self.calls.append(("update_customer", (customer_code, kwargs)))
        return {"customer_code": customer_code}

    def list_customer_authorizations(self, customer_code):
        self.calls.append(("list_customer_authorizations", customer_code))
        return []

    def deactivate_authorization(self, authorization_code):
        self.calls.append(("deactivate_authorization", authorization_code))
        return {"success": True}

    def verify_webhook_signature(self, payload, signature):
        self.calls.append(("verify_webhook_signature", (payload, signature)))
        return signature == "valid-signature"


@pytest.fixture
def gateway_with_fake_provider(monkeypatch):
    gateway = Gateway(provider="paystack", api_key="sk_test_key")
    fake = _FakeProvider()
    gateway._provider = fake
    return gateway, fake


def test_payments_facade_delegates_to_provider(gateway_with_fake_provider):
    gateway, fake = gateway_with_fake_provider
    gateway.payments.initialize(amount=1000, email="a@example.com")
    gateway.payments.verify("TXN_1")
    gateway.payments.charge_authorization(
        authorization_code="AUTH_1", email="a@example.com", amount=500
    )
    assert [call[0] for call in fake.calls] == [
        "initialize_payment",
        "verify_payment",
        "charge_authorization",
    ]


def test_customers_facade_delegates_to_provider(gateway_with_fake_provider):
    gateway, fake = gateway_with_fake_provider
    gateway.customers.create(email="a@example.com")
    gateway.customers.get("CUS_1")
    gateway.customers.update("CUS_1", phone="123")
    assert [call[0] for call in fake.calls] == [
        "create_customer",
        "get_customer",
        "update_customer",
    ]


def test_tokens_facade_delegates_to_provider(gateway_with_fake_provider):
    gateway, fake = gateway_with_fake_provider
    gateway.tokens.list_for_customer("CUS_1")
    gateway.tokens.deactivate("AUTH_1")
    assert [call[0] for call in fake.calls] == [
        "list_customer_authorizations",
        "deactivate_authorization",
    ]


def test_verify_webhook_returns_true_for_valid_signature(gateway_with_fake_provider):
    gateway, _ = gateway_with_fake_provider
    assert gateway.verify_webhook(b"payload", "valid-signature") is True


def test_verify_webhook_raises_for_invalid_signature(gateway_with_fake_provider):
    gateway, _ = gateway_with_fake_provider
    with pytest.raises(PaymentError):
        gateway.verify_webhook(b"payload", "bad-signature")


def test_initialize_rejects_invalid_email(gateway_with_fake_provider):
    gateway, fake = gateway_with_fake_provider
    with pytest.raises(ValidationError):
        gateway.payments.initialize(amount=1000, email="not-an-email")
    assert fake.calls == []


def test_initialize_rejects_non_positive_amount(gateway_with_fake_provider):
    gateway, fake = gateway_with_fake_provider
    with pytest.raises(ValidationError):
        gateway.payments.initialize(amount=0, email="a@example.com")
    assert fake.calls == []


def test_charge_authorization_rejects_invalid_input(gateway_with_fake_provider):
    gateway, fake = gateway_with_fake_provider
    with pytest.raises(ValidationError):
        gateway.payments.charge_authorization(
            authorization_code="AUTH_1", email="a@example.com", amount=-5
        )
    assert fake.calls == []


def test_customers_create_rejects_invalid_email(gateway_with_fake_provider):
    gateway, fake = gateway_with_fake_provider
    with pytest.raises(ValidationError):
        gateway.customers.create(email="not-an-email")
    assert fake.calls == []


def test_charge_authorization_idempotency_key_dedupes_within_gateway(
    gateway_with_fake_provider,
):
    gateway, fake = gateway_with_fake_provider
    first = gateway.payments.charge_authorization(
        authorization_code="AUTH_1",
        email="a@example.com",
        amount=500,
        idempotency_key="order-42",
    )
    second = gateway.payments.charge_authorization(
        authorization_code="AUTH_1",
        email="a@example.com",
        amount=500,
        idempotency_key="order-42",
    )
    assert first == second
    assert len(fake.calls) == 1


def test_charge_authorization_without_idempotency_key_always_calls_provider(
    gateway_with_fake_provider,
):
    gateway, fake = gateway_with_fake_provider
    gateway.payments.charge_authorization(
        authorization_code="AUTH_1", email="a@example.com", amount=500
    )
    gateway.payments.charge_authorization(
        authorization_code="AUTH_1", email="a@example.com", amount=500
    )
    assert len(fake.calls) == 2


class _FakeStorage(BaseStorage):
    def __init__(self):
        self.saved = []

    def save_transaction(self, transaction):
        self.saved.append(transaction)


def test_gateway_saves_transactions_through_storage():
    fake_storage = _FakeStorage()
    gateway = Gateway(provider="paystack", api_key="sk_test_key", storage=fake_storage)
    fake_provider = _FakeProvider()
    gateway._provider = fake_provider

    gateway.payments.initialize(amount=1000, email="a@example.com")
    gateway.payments.verify("TXN_1")
    gateway.payments.charge_authorization(
        authorization_code="AUTH_1", email="a@example.com", amount=500
    )

    assert fake_storage.saved == [
        {"reference": "TXN_1"},
        {"status": "success"},
        {"status": "success"},
    ]


def test_gateway_defaults_to_noop_storage():
    gateway = Gateway(provider="paystack", api_key="sk_test_key")
    gateway._provider = _FakeProvider()
    # Should not raise even though nothing was passed for `storage`.
    gateway.payments.verify("TXN_1")
