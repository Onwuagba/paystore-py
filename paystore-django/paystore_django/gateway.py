"""Settings-based Gateway factory for Django projects."""

from typing import Any, Dict, Optional

from django.conf import settings
from paystore import AsyncGateway, Gateway


def _paystore_settings() -> Dict[str, Any]:
    """
    Read the `PAYSTORE` dict from Django settings.

    Example:
        PAYSTORE = {
            "PROVIDER": "paystack",
            "ENVIRONMENT": "production",
            "API_KEY": env("PAYSTACK_SECRET_KEY"),   # optional
            "WEBHOOK_SECRET": env("PAYSTACK_WEBHOOK_SECRET"),  # optional
            "EXTRA": {},  # provider-specific kwargs, e.g. Remita's
                          # merchant_id/service_type_id/api_secret
        }

    Every key is optional: omit API_KEY/WEBHOOK_SECRET to fall back to
    paystore's own {PROVIDER}_SECRET_KEY/{PROVIDER}_WEBHOOK_SECRET env
    var resolution.
    """
    return getattr(settings, "PAYSTORE", {}) or {}


def _gateway_kwargs(provider: Optional[str]) -> Dict[str, Any]:
    config = _paystore_settings()
    extra = dict(config.get("EXTRA", {}))

    kwargs: Dict[str, Any] = {
        "provider": provider or config.get("PROVIDER"),
        "environment": config.get("ENVIRONMENT", "sandbox"),
        **extra,
    }
    if config.get("API_KEY"):
        kwargs["api_key"] = config["API_KEY"]
    if config.get("WEBHOOK_SECRET"):
        kwargs["webhook_secret"] = config["WEBHOOK_SECRET"]
    return kwargs


def get_gateway(provider: Optional[str] = None) -> Gateway:
    """
    Build a Gateway from Django settings.

    Args:
        provider: Overrides PAYSTORE["PROVIDER"] from settings — useful
            when a single Django project supports multiple gateways
            (e.g. choosing per-currency or per-request).
    """
    return Gateway(**_gateway_kwargs(provider))


def get_async_gateway(provider: Optional[str] = None) -> AsyncGateway:
    """
    Build an AsyncGateway from Django settings, for async views.

    Same PAYSTORE settings and `provider` override as get_gateway().
    """
    return AsyncGateway(**_gateway_kwargs(provider))
