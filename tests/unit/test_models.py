"""Tests for data models."""

from paystore.core.models import Transaction


def test_transaction_defaults():
    transaction = Transaction(
        reference="TXN_1", amount=1000, status="success", email="a@example.com"
    )
    assert transaction.currency == "NGN"
    assert transaction.authorization_url is None


def test_payment_from_raw_normalizes_status():
    from paystore.core.models import Payment, PaymentStatus

    payment = Payment.from_raw("stripe", {"reference": "r1", "status": "success"})
    assert payment.status is PaymentStatus.SUCCESS
    assert Payment.from_raw("x", {"status": "weird"}).status is PaymentStatus.UNKNOWN
