# Webhooks Guide

Webhooks are how a provider tells your app a payment actually completed
(or failed) — `initialize_payment` only creates a pending transaction;
you find out what happened by verifying either the customer's redirect
or, more reliably, the provider's webhook.

## Verifying a webhook

Every provider signs its webhook payloads differently, but paystore
gives you one method regardless of which one you're using:

```python
from paystore import Gateway
from paystore.core.exceptions import PaymentError

gateway = Gateway(provider="paystack")  # reads PAYSTACK_SECRET_KEY

def handle_webhook(raw_body: bytes, signature: str):
    try:
        gateway.verify_webhook(raw_body, signature)
    except PaymentError:
        # Reject it — do not trust the payload
        return

    # Safe to trust the payload now
    ...
```

`raw_body` must be the **exact, unparsed** request body — verifying a
re-serialized/re-encoded copy of the JSON will fail even if the data
looks identical, since signatures are computed over the raw bytes.

## Parsing the event

`verify_webhook` only tells you the signature is valid — you still had
to parse the JSON and figure out the event type/relevant object
yourself, and every provider shapes that differently (Paystack/
Flutterwave use an `"event"` field with the payload under `"data"`;
Stripe uses `"type"` with the object under `"data"."object"`).
`parse_webhook_event` verifies and normalizes both in one call:

```python
event = gateway.parse_webhook_event(raw_body, signature)  # raises PaymentError if invalid

print(event.event_type)  # e.g. "charge.success" (Paystack) / "checkout.session.completed" (Stripe)
print(event.data)        # the normalized object — {"reference": ..., "status": ...} etc.
print(event.raw)         # the full, unmodified parsed body — always available
```

`AsyncGateway` has the same method (`await gateway.parse_webhook_event(...)`).
Remita's payload shape isn't well-documented enough to normalize
confidently, so its events always come back with `event_type="unknown"`
and `data` equal to `raw` — use `event.raw` directly for it.

## Where the signature comes from

Each provider puts its signature in a different header. paystore ships
the mapping so you don't have to hardcode it:

```python
from paystore.webhooks.headers import SIGNATURE_HEADERS

SIGNATURE_HEADERS
# {
#     "paystack": "X-Paystack-Signature",
#     "flutterwave": "verif-hash",
#     "stripe": "Stripe-Signature",
#     "remita": "X-Remita-Signature",
# }
```

PayPal is deliberately not in this dict — it needs *several* header
values, not one, so it doesn't fit the "single signature string" model
the rest of this guide (and the generic Django/stdlib webhook views)
assumes. If you're using PayPal, build the `signature` argument
yourself as a JSON object of the relevant headers — see
`PaypalProvider.verify_webhook_signature`'s docstring for the exact
shape — rather than using `SIGNATURE_HEADERS`/the generic views as-is.

## Provider-specific signing secrets

Paystack and Remita sign webhooks with your `api_key`/`api_secret`, so
`Gateway(provider="paystack")` (or `remita`) is enough on its own.
Stripe and Flutterwave sign with a **separate** secret you must also
provide — set it explicitly or via `{PROVIDER}_WEBHOOK_SECRET`:

```bash
export STRIPE_WEBHOOK_SECRET=whsec_...
export FLUTTERWAVE_WEBHOOK_SECRET=...   # the dashboard secret hash
```

```python
gateway = Gateway(provider="stripe")  # picks up STRIPE_WEBHOOK_SECRET automatically
# or explicitly:
gateway = Gateway(provider="stripe", api_key="sk_test_...", webhook_secret="whsec_...")
```

Trying to verify a Stripe/Flutterwave webhook without a
`webhook_secret` raises `ConfigurationError` — see
[Provider Support](providers.md) for details on each provider's
signing scheme.

## Framework integration

- **Django**: use `paystore-django`'s `PaystoreWebhookView` — it
  handles the header lookup and verification for you. See
  [paystore-django's README](https://github.com/onwuagba/paystore-py/tree/main/paystore-django).
- **Everything else (FastAPI, Flask, plain Python)**: see
  [`examples/webhook_server_example.py`](https://github.com/onwuagba/paystore-py/blob/main/examples/webhook_server_example.py)
  — a minimal stdlib-only server showing the full verify → handle
  flow, adaptable to any framework.

## Local testing

You need a publicly reachable URL for a provider's dashboard to
actually deliver webhooks to you:

- **Stripe**: use the [Stripe CLI](https://stripe.com/docs/stripe-cli)
  — `stripe listen --forward-to localhost:8000/webhook` — no tunnel or
  dashboard registration needed.
- **Paystack / Flutterwave / Remita**: use a tunnel (ngrok or similar)
  and register the public URL as the webhook endpoint in the
  provider's dashboard.
