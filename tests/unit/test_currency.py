"""Tests for currency helpers."""

import pytest

from paystore.utils.currency import is_zero_decimal_currency


@pytest.mark.parametrize("currency", ["JPY", "jpy", "KRW", "VND", "XOF"])
def test_is_zero_decimal_currency_true(currency):
    assert is_zero_decimal_currency(currency) is True


@pytest.mark.parametrize("currency", ["USD", "NGN", "usd", "EUR", "GBP"])
def test_is_zero_decimal_currency_false(currency):
    assert is_zero_decimal_currency(currency) is False
