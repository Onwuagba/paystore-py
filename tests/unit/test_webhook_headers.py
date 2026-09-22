"""Tests for the shared webhook signature header registry."""

from paystore.webhooks.headers import SIGNATURE_HEADERS


def test_signature_headers_cover_every_provider():
    assert set(SIGNATURE_HEADERS) == {"paystack", "flutterwave", "stripe", "remita"}


def test_signature_headers_are_nonempty_strings():
    for header in SIGNATURE_HEADERS.values():
        assert isinstance(header, str) and header
