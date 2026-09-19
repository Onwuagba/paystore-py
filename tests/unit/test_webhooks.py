"""Tests for webhook verification."""

import pytest

from paystore.core.exceptions import PaymentError
from paystore.webhooks.verifier import WebhookVerifier


class _FakeProvider:
    def __init__(self, is_valid: bool):
        self._is_valid = is_valid

    def verify_webhook_signature(self, payload: bytes, signature: str) -> bool:
        return self._is_valid


def test_verify_returns_true_for_valid_signature():
    verifier = WebhookVerifier(_FakeProvider(is_valid=True))
    assert verifier.verify(b"payload", "sig") is True


def test_verify_raises_for_invalid_signature():
    verifier = WebhookVerifier(_FakeProvider(is_valid=False))
    with pytest.raises(PaymentError):
        verifier.verify(b"payload", "bad-sig")
