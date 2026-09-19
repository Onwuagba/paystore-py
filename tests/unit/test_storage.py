"""Tests for storage backends."""

from paystore.storage.base import NoOpStorage


def test_noop_storage_save_transaction_does_nothing():
    storage = NoOpStorage()
    assert storage.save_transaction({"reference": "TXN_1"}) is None
