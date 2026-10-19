"""Well-known webhook signature header names, by provider.

Shared by paystore-django's PaystoreWebhookView and
examples/webhook_server_example.py so there's one source of truth
instead of each framework integration keeping its own copy.
"""

import json
from typing import Callable, Optional

SIGNATURE_HEADERS = {
    "paystack": "X-Paystack-Signature",
    "flutterwave": "verif-hash",
    "stripe": "Stripe-Signature",
    "remita": "X-Remita-Signature",
}

# PayPal verification needs five headers rather than one; see
# build_signature, which packs them the way PaypalProvider expects.
PAYPAL_SIGNATURE_HEADERS = {
    "transmission_id": "PAYPAL-TRANSMISSION-ID",
    "transmission_time": "PAYPAL-TRANSMISSION-TIME",
    "cert_url": "PAYPAL-CERT-URL",
    "auth_algo": "PAYPAL-AUTH-ALGO",
    "transmission_sig": "PAYPAL-TRANSMISSION-SIG",
}


def build_signature(provider: str, get_header: Callable[[str], Optional[str]]) -> str:
    """
    Build the `signature` argument for Gateway.verify_webhook /
    parse_webhook_event from request headers.

    `get_header` takes a plain header name (e.g. "Stripe-Signature") and
    returns its value or None, so this works with any framework.
    """
    provider = provider.lower()
    if provider == "paypal":
        return json.dumps(
            {
                key: get_header(header) or ""
                for key, header in PAYPAL_SIGNATURE_HEADERS.items()
            }
        )
    header = SIGNATURE_HEADERS.get(provider)
    return (get_header(header) or "") if header else ""
