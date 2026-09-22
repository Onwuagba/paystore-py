"""Tests for DjangoORMStorage."""

import pytest

from paystore_django.models import PaystoreTransaction
from paystore_django.storage import DjangoORMStorage

pytestmark = pytest.mark.django_db


def test_save_transaction_creates_row():
    storage = DjangoORMStorage()
    storage.save_transaction(
        {
            "reference": "TXN_1",
            "status": "success",
            "amount": 1000,
            "currency": "NGN",
        }
    )

    row = PaystoreTransaction.objects.get(reference="TXN_1")
    assert row.status == "success"
    assert row.amount == 1000
    assert row.currency == "NGN"
    assert row.raw["reference"] == "TXN_1"


def test_save_transaction_upserts_on_reference():
    storage = DjangoORMStorage()
    storage.save_transaction({"reference": "TXN_1", "status": "pending"})
    storage.save_transaction({"reference": "TXN_1", "status": "success"})

    assert PaystoreTransaction.objects.filter(reference="TXN_1").count() == 1
    row = PaystoreTransaction.objects.get(reference="TXN_1")
    assert row.status == "success"


def test_save_transaction_skips_when_reference_missing():
    storage = DjangoORMStorage()
    storage.save_transaction({"status": "success"})
    assert PaystoreTransaction.objects.count() == 0


def test_save_transaction_stores_full_raw_payload():
    storage = DjangoORMStorage()
    transaction = {
        "reference": "TXN_2",
        "status": "success",
        "authorization_url": "https://pay.example/abc",
        "nested": {"foo": "bar"},
    }
    storage.save_transaction(transaction)

    row = PaystoreTransaction.objects.get(reference="TXN_2")
    assert row.raw == transaction


def test_str_representation():
    row = PaystoreTransaction.objects.create(reference="TXN_3", status="success")
    assert str(row) == "TXN_3 (success)"
