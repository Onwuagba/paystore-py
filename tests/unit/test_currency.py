"""Tests for currency helpers."""

import pytest

from paystore.utils.currency import is_zero_decimal_currency, to_decimal_string


@pytest.mark.parametrize("currency", ["JPY", "jpy", "KRW", "VND", "XOF"])
def test_is_zero_decimal_currency_true(currency):
    assert is_zero_decimal_currency(currency) is True


@pytest.mark.parametrize("currency", ["USD", "NGN", "usd", "EUR", "GBP"])
def test_is_zero_decimal_currency_false(currency):
    assert is_zero_decimal_currency(currency) is False


def test_to_decimal_string_converts_minor_units():
    assert to_decimal_string(1000, "USD") == "10.00"
    assert to_decimal_string(150, "USD") == "1.50"


def test_to_decimal_string_leaves_zero_decimal_currency_as_is():
    assert to_decimal_string(500, "JPY") == "500"
    assert to_decimal_string(500, "UGX") == "500"
