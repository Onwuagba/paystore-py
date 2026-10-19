"""Normalize provider subscription objects into paystore.core.models.Subscription."""

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from paystore.core.models import Subscription, SubscriptionStatus

_S = SubscriptionStatus

_STRIPE_STATUS = {
    "trialing": _S.TRIALING,
    "active": _S.ACTIVE,
    "past_due": _S.PAST_DUE,
    "unpaid": _S.UNPAID,
    "paused": _S.PAUSED,
    "incomplete": _S.INCOMPLETE,
    "incomplete_expired": _S.EXPIRED,
    "canceled": _S.CANCELED,
}

# PayPal's SUSPENDED covers both failed-payment and manual suspension;
# PAUSED is the closer neutral state.
_PAYPAL_STATUS = {
    "APPROVAL_PENDING": _S.INCOMPLETE,
    "APPROVED": _S.INCOMPLETE,
    "ACTIVE": _S.ACTIVE,
    "SUSPENDED": _S.PAUSED,
    "CANCELLED": _S.CANCELED,
    "EXPIRED": _S.EXPIRED,
}

_PAYSTACK_STATUS = {
    "active": _S.ACTIVE,
    "non-renewing": _S.ACTIVE,
    "attention": _S.PAST_DUE,
    "completed": _S.EXPIRED,
    "cancelled": _S.CANCELED,
}


def parse_datetime(value: Any) -> Optional[datetime]:
    """Parse an epoch (seconds) or ISO-8601 string into an aware UTC datetime."""
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, tz=timezone.utc)
    try:
        text = str(value).replace("Z", "+00:00")
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _stripe(raw: Dict[str, Any]) -> Subscription:
    items = (raw.get("items") or {}).get("data") or []
    item = items[0] if items else {}
    price = item.get("price") or item.get("plan") or {}
    customer = raw.get("customer")
    if isinstance(customer, dict):  # expanded
        customer = customer.get("id")
    # Newer API versions moved the billing period onto the subscription item.
    start = raw.get("current_period_start") or item.get("current_period_start")
    end = raw.get("current_period_end") or item.get("current_period_end")
    return Subscription(
        id=str(raw.get("id", "")),
        provider="stripe",
        status=_STRIPE_STATUS.get(str(raw.get("status")), _S.UNKNOWN),
        plan_id=price.get("id"),
        customer_id=customer,
        quantity=item.get("quantity") or raw.get("quantity") or 1,
        current_period_start=parse_datetime(start),
        current_period_end=parse_datetime(end),
        trial_end=parse_datetime(raw.get("trial_end")),
        cancel_at_period_end=bool(raw.get("cancel_at_period_end")),
        canceled_at=parse_datetime(raw.get("canceled_at")),
        raw=raw,
    )


def _paypal(raw: Dict[str, Any]) -> Subscription:
    billing = raw.get("billing_info") or {}
    last_payment = billing.get("last_payment") or {}
    subscriber = raw.get("subscriber") or {}
    status = _PAYPAL_STATUS.get(str(raw.get("status")), _S.UNKNOWN)
    return Subscription(
        id=str(raw.get("id", "")),
        provider="paypal",
        status=status,
        plan_id=raw.get("plan_id"),
        customer_id=subscriber.get("payer_id"),
        quantity=int(raw.get("quantity") or 1),
        current_period_start=parse_datetime(last_payment.get("time")),
        current_period_end=parse_datetime(billing.get("next_billing_time")),
        canceled_at=(
            parse_datetime(raw.get("status_update_time"))
            if status is _S.CANCELED
            else None
        ),
        raw=raw,
    )


def _paystack(raw: Dict[str, Any]) -> Subscription:
    plan = raw.get("plan") or {}
    customer = raw.get("customer") or {}
    return Subscription(
        id=str(raw.get("subscription_code", raw.get("id", ""))),
        provider="paystack",
        status=_PAYSTACK_STATUS.get(str(raw.get("status")), _S.UNKNOWN),
        plan_id=plan.get("plan_code"),
        customer_id=customer.get("customer_code"),
        quantity=int(raw.get("quantity") or 1),
        current_period_end=parse_datetime(raw.get("next_payment_date")),
        cancel_at_period_end=raw.get("status") == "non-renewing",
        raw=raw,
    )


_PARSERS = {"stripe": _stripe, "paypal": _paypal, "paystack": _paystack}


def parse_subscription(provider: str, raw: Dict[str, Any]) -> Subscription:
    """
    Build a Subscription from a provider's raw subscription object.

    Raises ValueError for a provider with no subscription support.
    """
    parser = _PARSERS.get(provider.lower())
    if parser is None:
        raise ValueError(f"No subscription parser for provider {provider!r}")
    return parser(raw)
