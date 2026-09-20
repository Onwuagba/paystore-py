"""Tests for input validation utilities."""

import pytest

from paystore.core.exceptions import ValidationError
from paystore.security.validation import validate_amount, validate_email


@pytest.mark.parametrize(
    "email",
    [
        "user@example.com",
        "first.last@example.co.uk",
        "user+tag@example.io",
    ],
)
def test_validate_email_accepts_valid_addresses(email):
    assert validate_email(email) is True


@pytest.mark.parametrize(
    "email",
    [
        "not-an-email",
        "missing-domain@",
        "@missing-local.com",
        "spaces in@email.com",
    ],
)
def test_validate_email_rejects_invalid_addresses(email):
    with pytest.raises(ValidationError):
        validate_email(email)


def test_validate_email_error_message_interpolates_email():
    with pytest.raises(ValidationError, match="bad-email"):
        validate_email("bad-email")


def test_validate_amount_accepts_positive():
    assert validate_amount(100) is True


@pytest.mark.parametrize("amount", [0, -1, -100])
def test_validate_amount_rejects_non_positive(amount):
    with pytest.raises(ValidationError):
        validate_amount(amount)


@pytest.mark.parametrize("amount", [10.5, "1000", None, True, False])
def test_validate_amount_rejects_non_int(amount):
    with pytest.raises(ValidationError, match="must be an int"):
        validate_amount(amount)
