"""Well-known webhook signature header names, by provider.

Shared by paystore-django's PaystoreWebhookView and
examples/webhook_server_example.py so there's one source of truth
instead of each framework integration keeping its own copy.
"""

SIGNATURE_HEADERS = {
    "paystack": "X-Paystack-Signature",
    "flutterwave": "verif-hash",
    "stripe": "Stripe-Signature",
    "remita": "X-Remita-Signature",
}
