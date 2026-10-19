"""Tests for the shared webhook signature header registry."""

import json

from paystore.webhooks.headers import SIGNATURE_HEADERS, build_signature


def test_signature_headers_cover_every_provider():
    assert set(SIGNATURE_HEADERS) == {"paystack", "flutterwave", "stripe", "remita"}


def test_signature_headers_are_nonempty_strings():
    for header in SIGNATURE_HEADERS.values():
        assert isinstance(header, str) and header


def test_build_signature_single_header_providers():
    headers = {"Stripe-Signature": "t=1,v1=abc"}
    assert build_signature("stripe", headers.get) == "t=1,v1=abc"
    assert build_signature("paystack", headers.get) == ""
    assert build_signature("momo", headers.get) == ""


def test_build_signature_packs_paypal_headers_as_json():
    headers = {
        "PAYPAL-TRANSMISSION-ID": "id",
        "PAYPAL-TRANSMISSION-TIME": "time",
        "PAYPAL-CERT-URL": "https://cert",
        "PAYPAL-AUTH-ALGO": "SHA256withRSA",
        "PAYPAL-TRANSMISSION-SIG": "sig",
    }
    assert json.loads(build_signature("PayPal", headers.get)) == {
        "transmission_id": "id",
        "transmission_time": "time",
        "cert_url": "https://cert",
        "auth_algo": "SHA256withRSA",
        "transmission_sig": "sig",
    }
