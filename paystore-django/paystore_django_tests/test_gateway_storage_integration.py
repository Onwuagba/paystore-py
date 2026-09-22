"""Integration test: get_gateway(storage=...) actually persists results."""

import pytest

from paystore_django import get_gateway
from paystore_django.models import PaystoreTransaction
from paystore_django.storage import DjangoORMStorage

pytestmark = pytest.mark.django_db


class _FakeProvider:
    def __init__(self, config=None):
        pass

    def initialize_payment(self, **kwargs):
        return {
            "reference": "TXN_int_1",
            "status": "pending",
            "amount": kwargs["amount"],
        }


def test_get_gateway_with_django_storage_persists_transaction():
    gateway = get_gateway(storage=DjangoORMStorage())
    gateway._provider = _FakeProvider()

    gateway.payments.initialize(amount=1000, email="a@example.com")

    row = PaystoreTransaction.objects.get(reference="TXN_int_1")
    assert row.status == "pending"
    assert row.amount == 1000
