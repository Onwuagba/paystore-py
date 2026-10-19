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
    # Set when a change (e.g. a PayPal seat revision) only takes effect
    # once the customer follows this link.
    approval_url: Optional[str] = None
    raw: Dict[str, Any] = Field(default_factory=dict)


class PaymentStatus(str, Enum):
    """Provider-neutral payment states."""

    SUCCESS = "success"
    PENDING = "pending"
    FAILED = "failed"
    CANCELLED = "cancelled"
    UNKNOWN = "unknown"


class Payment(BaseModel):
    """
    A verified payment or checkout session, normalized across providers.

    amount is in minor units and currency upper-case where the provider
    reports them (Stripe, Paystack, PayPal); None otherwise.
    `subscription_id` is set for a completed subscription-mode checkout.
    `raw` is the provider's full response.
    """

    reference: str
    provider: str
    status: PaymentStatus = PaymentStatus.UNKNOWN
    amount: Optional[int] = None
    currency: Optional[str] = None
    customer_id: Optional[str] = None
    subscription_id: Optional[str] = None
    raw: Dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def from_raw(cls, provider: str, raw: Dict[str, Any]) -> "Payment":
        from paystore.core.payments import extract_payment_fields

        try:
            status = PaymentStatus(str(raw.get("status")).lower())
        except ValueError:
            status = PaymentStatus.UNKNOWN
        return cls(
            reference=str(raw.get("reference", "")),
            provider=provider,
            status=status,
            raw=raw,
            **extract_payment_fields(provider, raw),
        )


class InvoiceStatus(str, Enum):
    """Provider-neutral invoice states."""

    DRAFT = "draft"
    OPEN = "open"
    PAID = "paid"
    FAILED = "failed"
    UNCOLLECTIBLE = "uncollectible"
    VOID = "void"
    UNKNOWN = "unknown"


class Invoice(BaseModel):
    """
    A subscription invoice / billing attempt, normalized across providers.

    Amounts are minor units. `hosted_url`/`pdf_url` are Stripe-only.
    `attempt_count` and `next_attempt_at` drive dunning: Stripe reports
    both; PayPal/Paystack leave them None.
    """

    id: str
    provider: str
    number: Optional[str] = None
    status: InvoiceStatus = InvoiceStatus.UNKNOWN
    amount_due: Optional[int] = None
    amount_paid: Optional[int] = None
    currency: Optional[str] = None
    hosted_url: Optional[str] = None
    pdf_url: Optional[str] = None
    subscription_id: Optional[str] = None
    customer_id: Optional[str] = None
    attempt_count: Optional[int] = None
    next_attempt_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    raw: Dict[str, Any] = Field(default_factory=dict)
