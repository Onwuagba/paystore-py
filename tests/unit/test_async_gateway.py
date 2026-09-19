"""Tests for AsyncGateway."""

import pytest

from paystore.core.async_gateway import AsyncGateway
from paystore.core.exceptions import PaymentError


class _FakeProvider:
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
def async_gateway_with_fake_provider():
    gateway = AsyncGateway(provider="paystack", api_key="sk_test_key")
    fake = _FakeProvider()
    gateway._gateway._provider = fake
    return gateway, fake


@pytest.mark.asyncio
async def test_initialize_payment(async_gateway_with_fake_provider):
    gateway, fake = async_gateway_with_fake_provider
    result = await gateway.initialize_payment(1000, "a@example.com")
    assert result["reference"] == "TXN_1"
    assert fake.calls[0][0] == "initialize_payment"


@pytest.mark.asyncio
async def test_verify_payment(async_gateway_with_fake_provider):
    gateway, fake = async_gateway_with_fake_provider
    result = await gateway.verify_payment("TXN_1")
    assert result["status"] == "success"
    assert fake.calls[0] == ("verify_payment", "TXN_1")


@pytest.mark.asyncio
async def test_charge_authorization(async_gateway_with_fake_provider):
    gateway, fake = async_gateway_with_fake_provider
    result = await gateway.charge_authorization("AUTH_1", "a@example.com", 500)
    assert result["status"] == "success"
    assert fake.calls[0][0] == "charge_authorization"


@pytest.mark.asyncio
async def test_customer_and_token_methods(async_gateway_with_fake_provider):
    gateway, fake = async_gateway_with_fake_provider
    await gateway.create_customer("a@example.com")
    await gateway.get_customer("CUS_1")
    await gateway.update_customer("CUS_1", phone="123")
    await gateway.list_tokens("CUS_1")
    await gateway.deactivate_token("AUTH_1")
    assert [call[0] for call in fake.calls] == [
        "create_customer",
        "get_customer",
        "update_customer",
        "list_customer_authorizations",
        "deactivate_authorization",
    ]


@pytest.mark.asyncio
async def test_verify_webhook_returns_true_for_valid_signature(
    async_gateway_with_fake_provider,
):
    gateway, _ = async_gateway_with_fake_provider
    assert await gateway.verify_webhook(b"payload", "valid-signature") is True


@pytest.mark.asyncio
async def test_verify_webhook_raises_for_invalid_signature(
    async_gateway_with_fake_provider,
):
    gateway, _ = async_gateway_with_fake_provider
    with pytest.raises(PaymentError):
        await gateway.verify_webhook(b"payload", "bad-signature")


def test_config_property_exposes_sync_gateways_config():
    gateway = AsyncGateway(provider="paystack", api_key="sk_test_key")
    assert gateway.config.provider == "paystack"
