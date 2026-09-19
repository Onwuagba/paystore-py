"""Tests for the settings-based Gateway factory."""

from django.test import override_settings
from paystore.providers.flutterwave.provider import FlutterwaveProvider
from paystore.providers.paystack.provider import PaystackProvider

from paystore_django.gateway import get_gateway


def test_get_gateway_uses_paystore_settings():
    gateway = get_gateway()
    assert isinstance(gateway._provider, PaystackProvider)
    assert gateway.config.api_key == "sk_test_mock"
    assert gateway.config.webhook_secret == "whsec_mock"


def test_get_gateway_provider_override():
    gateway = get_gateway(provider="flutterwave")
    assert isinstance(gateway._provider, FlutterwaveProvider)


@override_settings(PAYSTORE={})
def test_get_gateway_falls_back_to_env_vars(monkeypatch):
    monkeypatch.setenv("PAYSTACK_SECRET_KEY", "sk_test_from_env")
    gateway = get_gateway(provider="paystack")
    assert gateway.config.api_key == "sk_test_from_env"


@override_settings(
    PAYSTORE={
        "PROVIDER": "remita",
        "API_KEY": "test_key",
        "EXTRA": {
            "api_secret": "test_secret",
            "merchant_id": "MERCHANT_1",
            "service_type_id": "SERVICE_1",
        },
    }
)
def test_get_gateway_passes_extra_kwargs():
    gateway = get_gateway()
    assert gateway.config.merchant_id == "MERCHANT_1"
    assert gateway.config.service_type_id == "SERVICE_1"
