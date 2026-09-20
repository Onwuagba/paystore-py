"""Configuration management."""

from typing import Any, List, Optional, Tuple

from pydantic import BaseModel, Field, field_validator

_MASKED_FIELDS = {"api_key", "api_secret", "webhook_secret"}


def _mask(value: str) -> str:
    if len(value) <= 4:
        return "***"
    return f"***{value[-4:]}"


class Config(BaseModel):
    """
    Configuration for the payment gateway.

    Secrets (api_key, api_secret, webhook_secret) are masked in repr()/
    str() so printing or logging a Config by accident doesn't leak them
    in plaintext.
    """

    provider: str = Field(..., description="Payment provider name")
    api_key: str = Field(..., description="Provider API key")
    environment: str = Field(default="sandbox", description="Environment")
    timeout: int = Field(default=30, description="Request timeout")
    webhook_secret: Optional[str] = Field(
        default=None,
        description=(
            "Secret used to verify webhook signatures. Required by providers "
            "that sign webhooks with a value other than the API key "
            "(e.g. Stripe's whsec_..., Flutterwave's dashboard secret hash)."
        ),
    )
    api_secret: Optional[str] = Field(
        default=None,
        description=(
            "Secondary secret some providers use alongside api_key "
            "(e.g. Remita's request-signing secret)."
        ),
    )
    merchant_id: Optional[str] = Field(
        default=None, description="Merchant/business id (required by Remita)."
    )
    service_type_id: Optional[str] = Field(
        default=None,
        description="Service type id for the transaction (required by Remita).",
    )

    @field_validator("environment")
    @classmethod
    def validate_environment(cls, v: str) -> str:
        if v not in ("sandbox", "production"):
            raise ValueError("Environment must be 'sandbox' or 'production'")
        return v

    def __repr_args__(self) -> List[Tuple[Optional[str], Any]]:
        return [
            (name, _mask(value) if name in _MASKED_FIELDS and value else value)
            for name, value in super().__repr_args__()
        ]
