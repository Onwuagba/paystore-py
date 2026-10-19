"""Tests for subscription normalization."""

from datetime import datetime, timezone

import pytest

from paystore.core.models import SubscriptionStatus
from paystore.core.subscriptions import parse_datetime, parse_subscription


def test_stripe_subscription_normalizes_fields():
    raw = {
        "id": "sub_1",
        "status": "trialing",
        "customer": "cus_1",
        "cancel_at_period_end": True,
        "trial_end": 1700000000,
        "canceled_at": None,
        "items": {
            "data": [
                {
                    "id": "si_1",
                    "quantity": 5,
                    "price": {"id": "price_1"},
                    "current_period_start": 1690000000,
                    "current_period_end": 1700000000,
                }
            ]
        },
    }
    sub = parse_subscription("stripe", raw)
    assert sub.status is SubscriptionStatus.TRIALING
    assert (sub.plan_id, sub.customer_id, sub.quantity) == ("price_1", "cus_1", 5)
    assert sub.cancel_at_period_end is True
    assert sub.current_period_end == datetime.fromtimestamp(1700000000, timezone.utc)
    assert sub.raw == raw


@pytest.mark.parametrize(
    "stripe_status, expected",
    [
        ("active", SubscriptionStatus.ACTIVE),
        ("past_due", SubscriptionStatus.PAST_DUE),
        ("canceled", SubscriptionStatus.CANCELED),
        ("unpaid", SubscriptionStatus.UNPAID),
        ("incomplete_expired", SubscriptionStatus.EXPIRED),
        ("something_new", SubscriptionStatus.UNKNOWN),
    ],
)
def test_stripe_status_mapping(stripe_status, expected):
    assert (
        parse_subscription("stripe", {"id": "s", "status": stripe_status}).status
        is expected
    )


def test_paypal_subscription_normalizes_fields():
    raw = {
        "id": "I-1",
        "status": "ACTIVE",
        "plan_id": "P-1",
        "quantity": "3",
        "subscriber": {"payer_id": "PAYER"},
        "billing_info": {
            "next_billing_time": "2026-11-01T10:00:00Z",
            "last_payment": {"time": "2026-10-01T10:00:00Z"},
        },
    }
    sub = parse_subscription("paypal", raw)
    assert sub.status is SubscriptionStatus.ACTIVE
    assert (sub.plan_id, sub.customer_id, sub.quantity) == ("P-1", "PAYER", 3)
    assert sub.current_period_end == datetime(2026, 11, 1, 10, tzinfo=timezone.utc)


def test_paypal_cancelled_and_suspended():
    assert (
        parse_subscription("paypal", {"id": "I", "status": "CANCELLED"}).status
        is SubscriptionStatus.CANCELED
    )
    assert (
        parse_subscription("paypal", {"id": "I", "status": "SUSPENDED"}).status
        is SubscriptionStatus.PAUSED
    )
    assert (
        parse_subscription("paypal", {"id": "I", "status": "APPROVAL_PENDING"}).status
        is SubscriptionStatus.INCOMPLETE
    )


def test_paystack_non_renewing_is_active_but_cancelling():
    sub = parse_subscription(
        "paystack",
        {
            "subscription_code": "SUB_1",
            "status": "non-renewing",
            "plan": {"plan_code": "PLN_1"},
        },
    )
    assert sub.status is SubscriptionStatus.ACTIVE
    assert sub.cancel_at_period_end is True
    assert sub.plan_id == "PLN_1"


def test_unsupported_provider_raises():
    with pytest.raises(ValueError):
        parse_subscription("flutterwave", {})


def test_parse_datetime_handles_none_garbage_and_naive():
    assert parse_datetime(None) is None
    assert parse_datetime("not a date") is None
    assert parse_datetime("2026-01-01T00:00:00").tzinfo is not None
