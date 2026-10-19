"""Data models."""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class Transaction(BaseModel):
    """Payment transaction model."""

    reference: str
    amount: int
    currency: str = "NGN"
    status: str
    email: str
    authorization_url: Optional[str] = None


class SubscriptionStatus(str, Enum):
    """Provider-neutral subscription lifecycle states."""

    TRIALING = "trialing"
    ACTIVE = "active"
    PAST_DUE = "past_due"
    UNPAID = "unpaid"
    PAUSED = "paused"
    INCOMPLETE = "incomplete"
    CANCELED = "canceled"
    EXPIRED = "expired"
    UNKNOWN = "unknown"


class Subscription(BaseModel):
    """
    A subscription, normalized across providers.

    `status` is the neutral state; `raw` is the provider's untouched
    object for anything not modeled here. `cancel_at_period_end` is True
    when the subscription is still live but won't renew.
    """

    id: str
    provider: str
    status: SubscriptionStatus = SubscriptionStatus.UNKNOWN
    plan_id: Optional[str] = None
    customer_id: Optional[str] = None
    quantity: int = 1
    current_period_start: Optional[datetime] = None
    current_period_end: Optional[datetime] = None
    trial_end: Optional[datetime] = None
    cancel_at_period_end: bool = False
    canceled_at: Optional[datetime] = None
    raw: Dict[str, Any] = Field(default_factory=dict)


class PaymentStatus(str, Enum):
    """Provider-neutral payment states."""

    SUCCESS = "success"
    PENDING = "pending"
    FAILED = "failed"
    CANCELLED = "cancelled"
    UNKNOWN = "unknown"


class Payment(BaseModel):
    """A verified payment, normalized across providers (`raw` = provider response)."""

    reference: str
    provider: str
    status: PaymentStatus = PaymentStatus.UNKNOWN
    raw: Dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def from_raw(cls, provider: str, raw: Dict[str, Any]) -> "Payment":
        try:
            status = PaymentStatus(str(raw.get("status")).lower())
        except ValueError:
            status = PaymentStatus.UNKNOWN
        return cls(
            reference=str(raw.get("reference", "")),
            provider=provider,
            status=status,
            raw=raw,
        )
