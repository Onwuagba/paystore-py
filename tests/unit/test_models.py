"""Tests for data models."""

from paystore.core.models import Transaction


def test_transaction_defaults():
    transaction = Transaction(
        reference="TXN_1", amount=1000, status="success", email="a@example.com"
    )
    assert transaction.currency == "NGN"
    assert transaction.authorization_url is None
