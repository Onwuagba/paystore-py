"""Typed wrapper around a verified webhook payload."""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Optional

from paystore.core.models import Subscription
from paystore.core.subscriptions import parse_datetime, parse_subscription

# Provider -> the raw payload key holding the event type/name.
_EVENT_TYPE_KEYS = {
    "paystack": "event",
    "flutterwave": "event",
    "stripe": "type",
    "paypal": "event_type",
}

# Provider -> the raw payload key holding the event's data object.
_DATA_KEYS = {"paypal": "resource"}

UNKNOWN = "unknown"

# Provider event name -> paystore's neutral `type`. Anything not listed
# maps to "unknown" — check `event_type`/`raw` for those.
_CANONICAL_TYPES = {
    "stripe": {
        "checkout.session.completed": "checkout.completed",
        "checkout.session.async_payment_succeeded": "payment.succeeded",
        "checkout.session.async_payment_failed": "payment.failed",
        "payment_intent.succeeded": "payment.succeeded",
        "payment_intent.payment_failed": "payment.failed",
        "charge.refunded": "refund.processed",
        "customer.subscription.created": "subscription.created",
        "customer.subscription.updated": "subscription.updated",
        "customer.subscription.deleted": "subscription.canceled",
        "invoice.paid": "invoice.paid",
        "invoice.payment_failed": "invoice.payment_failed",
    },
    "paystack": {
        "charge.success": "payment.succeeded",
        "refund.processed": "refund.processed",
        "subscription.create": "subscription.created",
        "subscription.disable": "subscription.canceled",
        "subscription.not_renew": "subscription.updated",
        "invoice.payment_failed": "invoice.payment_failed",
    },
    "flutterwave": {
        # charge.completed also fires for failed charges — see _flutterwave_type.
        "charge.completed": "payment.succeeded",
    },
    "paypal": {
        "PAYMENT.CAPTURE.COMPLETED": "payment.succeeded",
        "PAYMENT.CAPTURE.DENIED": "payment.failed",
        "PAYMENT.CAPTURE.DECLINED": "payment.failed",
        "PAYMENT.CAPTURE.REFUNDED": "refund.processed",
        "BILLING.SUBSCRIPTION.CREATED": "subscription.created",
        "BILLING.SUBSCRIPTION.ACTIVATED": "subscription.updated",
        "BILLING.SUBSCRIPTION.RE-ACTIVATED": "subscription.updated",
        "BILLING.SUBSCRIPTION.UPDATED": "subscription.updated",
        "BILLING.SUBSCRIPTION.SUSPENDED": "subscription.updated",
        "BILLING.SUBSCRIPTION.CANCELLED": "subscription.canceled",
        "BILLING.SUBSCRIPTION.EXPIRED": "subscription.canceled",
        "BILLING.SUBSCRIPTION.PAYMENT.FAILED": "invoice.payment_failed",
        "PAYMENT.SALE.COMPLETED": "invoice.paid",
    },
}


def _canonical_type(provider: str, event_type: str, data: Dict[str, Any]) -> str:
    if provider == "flutterwave" and event_type == "charge.completed":
        return (
            "payment.succeeded"
            if str(data.get("status")).lower() == "successful"
            else "payment.failed"
        )
    return _CANONICAL_TYPES.get(provider, {}).get(event_type, UNKNOWN)


def _event_id(provider: str, raw: Dict[str, Any]) -> Optional[str]:
    # Only Stripe and PayPal put a unique event id at the top level.
    if provider in ("stripe", "paypal") and raw.get("id"):
        return str(raw["id"])
    return None


def _created_at(provider: str, raw: Dict[str, Any]) -> Optional[datetime]:
    if provider == "stripe":
        return parse_datetime(raw.get("created"))
    if provider == "paypal":
        return parse_datetime(raw.get("create_time"))
    return None


def _subscription(
    provider: str, canonical: str, data: Dict[str, Any]
) -> Optional[Subscription]:
    """Parse the subscription object, for events whose data is one."""
    if not canonical.startswith("subscription."):
        return None
    try:
        return parse_subscription(provider, data)
    except ValueError:
        return None


@dataclass(frozen=True)
class WebhookEvent:
    """
    A verified webhook event, normalized across providers where possible.

    - `event_type` is the provider's own event name, unchanged.
    - `type` is paystore's neutral name — "payment.succeeded",
      "payment.failed", "refund.processed", "checkout.completed",
      "subscription.created" / ".updated" / ".canceled",
      "invoice.paid", "invoice.payment_failed" — or "unknown" for
      events not mapped (use `event_type`/`raw` for those).
    - `id` and `created_at` come from the provider where it supplies
      them (Stripe, PayPal); None otherwise. Use `id` to dedupe
      redelivered webhooks.
    - `subscription` is a normalized Subscription for subscription.*
      events (reflecting the state at the time of the event).
    - `data` is the provider's event object; `raw` the full unmodified
      body, the fallback for a provider (like Remita) whose payload
      shape isn't documented well enough to normalize.
    """

    provider: str
    event_type: str
    data: Dict[str, Any]
    raw: Dict[str, Any]
    type: str = UNKNOWN
    id: Optional[str] = None
    created_at: Optional[datetime] = None
    subscription: Optional[Subscription] = None

    @classmethod
    def from_raw(cls, provider: str, raw: Dict[str, Any]) -> "WebhookEvent":
        provider = provider.lower()
        event_type_key = _EVENT_TYPE_KEYS.get(provider)
        event_type = (
            str(raw.get(event_type_key, UNKNOWN)) if event_type_key else UNKNOWN
        )

        data = raw.get(_DATA_KEYS.get(provider, "data"), raw)
        # Stripe nests the actual object one level deeper, under data.object.
        if provider == "stripe" and isinstance(data, dict) and "object" in data:
            data = data["object"]
        if not isinstance(data, dict):
            data = {}

        canonical = _canonical_type(provider, event_type, data)
        return cls(
            provider=provider,
            event_type=event_type,
            data=data,
            raw=raw,
            type=canonical,
            id=_event_id(provider, raw),
            created_at=_created_at(provider, raw),
            subscription=_subscription(provider, canonical, data),
        )
