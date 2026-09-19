"""Tests for tokenization helpers."""

from datetime import datetime, timedelta

import pytest

from paystore.security.tokenization import RecurringPaymentHelper, TokenManager


def _authorization(**overrides):
    base = {
        "reusable": True,
        "brand": "visa",
        "last4": "4242",
        "exp_month": "12",
        "exp_year": "2099",
        "bank": "Test Bank",
        "country_code": "NG",
    }
    base.update(overrides)
    return base


def test_is_reusable():
    assert TokenManager.is_reusable(_authorization(reusable=True)) is True
    assert TokenManager.is_reusable(_authorization(reusable=False)) is False


def test_is_expired_false_for_future_card():
    assert (
        TokenManager.is_expired(_authorization(exp_month="12", exp_year="2099"))
        is False
    )


def test_is_expired_true_for_past_card():
    assert (
        TokenManager.is_expired(_authorization(exp_month="1", exp_year="2000")) is True
    )


def test_is_expired_false_when_missing_expiry():
    assert TokenManager.is_expired({"reusable": True}) is False


def test_get_card_info_includes_derived_flags():
    info = TokenManager.get_card_info(_authorization())
    assert info["brand"] == "visa"
    assert info["last4"] == "4242"
    assert info["is_reusable"] is True
    assert info["is_expired"] is False


def test_format_card_display():
    display = TokenManager.format_card_display(_authorization())
    assert display == "Visa •••• 4242 (Expires 12/2099)"


def test_filter_active_tokens_excludes_expired_and_non_reusable():
    tokens = [
        _authorization(),
        _authorization(reusable=False),
        _authorization(exp_month="1", exp_year="2000"),
    ]
    active = TokenManager.filter_active_tokens(tokens)
    assert len(active) == 1


@pytest.mark.parametrize(
    "interval,delta_days",
    [("daily", 1), ("weekly", 7)],
)
def test_calculate_next_charge_date_daily_weekly(interval, delta_days):
    start = datetime(2026, 1, 1)
    next_date = RecurringPaymentHelper.calculate_next_charge_date(start, interval)
    assert next_date == start + timedelta(days=delta_days)


def test_calculate_next_charge_date_monthly_rolls_over_year():
    start = datetime(2026, 12, 15)
    next_date = RecurringPaymentHelper.calculate_next_charge_date(start, "monthly")
    assert next_date == datetime(2027, 1, 15)


def test_calculate_next_charge_date_yearly():
    start = datetime(2026, 3, 5)
    next_date = RecurringPaymentHelper.calculate_next_charge_date(start, "yearly")
    assert next_date == datetime(2027, 3, 5)


def test_calculate_next_charge_date_invalid_interval_raises():
    with pytest.raises(ValueError):
        RecurringPaymentHelper.calculate_next_charge_date(datetime.now(), "hourly")
