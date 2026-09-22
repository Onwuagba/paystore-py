# Paystore

A unified Python library for integrating multiple payment providers, so
switching gateways is a one-line change instead of a rewrite.

## Features

- Multi-provider support: Paystack, Flutterwave, Stripe, Remita, PayPal
- Swap providers by changing one string — `initialize`/`verify`/
  `charge_authorization` return a consistent shape (`reference`,
  `authorization_url`, `status`) across all of them
- Saved cards / recurring charges via `charge_authorization` and
  customer management (Paystack and Stripe; see
  [provider support](#provider-support))
- Webhook signature verification per provider
- Credentials resolved from explicit args, env vars, or framework
  settings (see [docs/guides/authentication.md](https://github.com/onwuagba/paystore-py/blob/main/docs/guides/authentication.md))
- `idempotency_key` on `charge_authorization` to safely retry a charge
  without double-charging; input validation and richer exceptions
  (`AuthenticationError`, `RateLimitError`, `NetworkError`) so callers
  can tell retryable failures from permanent ones
- `AsyncGateway` for FastAPI/async Django (see [Async usage](#async-usage))

## Installation

### Using pip (recommended for users)

```bash
pip install paystore
```

### Using Poetry (recommended for contributors)

```bash
poetry add paystore
```

### From source

```bash
git clone https://github.com/onwuagba/paystore-py.git
cd paystore-py

# With Poetry
poetry install

# With pip
pip install -r requirements.txt
```

## Quick Start

```python
from paystore import Gateway

gateway = Gateway(
    provider="paystack",
    api_key="your_key",
    environment="sandbox"
)

transaction = gateway.payments.initialize(
    amount=10000,
    email="customer@example.com"
)
print(transaction["authorization_url"])  # send the customer here to pay

result = gateway.payments.verify(transaction["reference"])
print(result["status"])  # "success", "pending", or "failed"
```

Switching providers is a one-line change:

```python
gateway = Gateway(provider="flutterwave", api_key="FLWSECK_TEST-...")
# or
gateway = Gateway(provider="stripe", api_key="sk_test_...")
# Remita needs a few extra fields (see Provider Support below)
gateway = Gateway(
    provider="remita",
    api_key="...",
    api_secret="...",
    merchant_id="...",
    service_type_id="...",
)
```

## Provider Support

| Capability | Paystack | Flutterwave | Stripe | Remita | PayPal |
|---|---|---|---|---|---|
| Initialize / verify payment | ✅ | ✅ | ✅ | ✅ | ✅ |
| Charge saved card (`charge_authorization`) | ✅ | ✅ | ✅ | ❌ | ❌ |
| Webhook signature verification | ✅ | ✅ | ✅ | ✅ | ✅ |
| Customer management (`gateway.customers`) | ✅ | ❌ | ✅ | ❌ | ❌ |
| List/deactivate saved cards (`gateway.tokens`) | ✅ | ❌ | ✅ | ❌ | ❌ |
| Refunds (`gateway.payments.refund`) | ✅ | ✅ | ✅ | ❌ | ✅ |
| Recurring billing (`gateway.subscriptions`) | ✅ | ❌ | ✅ | ❌ | ❌ |
| Transfers/payouts (`gateway.transfers`) | ✅ | ✅ | ❌ | ❌ | ❌ |
| Split payments (`gateway.subaccounts`) | ✅ | ✅ | ➖ (passthrough kwargs) | ❌ | ❌ |

Check a provider's support in code instead of catching
`NotImplementedError`:

```python
if gateway.supports("customers"):
    gateway.customers.create(email="customer@example.com")
```

Notes:

- Flutterwave has no first-class "saved customer" API comparable to
  Paystack's or Stripe's, so `gateway.customers` and `gateway.tokens`
  raise `NotImplementedError` for that provider; recurring charges still
  work via `charge_authorization` using the card token from a verified
  transaction. Flutterwave's own recurring-billing model attaches a
  `payment_plan` to `initialize_payment` directly rather than a separate
  subscribe/cancel API per customer, so `gateway.subscriptions` isn't
  implemented for it either — pass `payment_plan=...` to `initialize`.
- Stripe does not support NGN — pass a currency it supports (e.g.
  `currency="USD"`). Zero-decimal currencies (JPY, KRW, etc.) don't get
  multiplied by 100 — see `paystore.utils.currency.is_zero_decimal_currency`.
- Remita uses an RRR (Remita Retrieval Reference) flow instead of
  charge-by-token, so `charge_authorization`, customer management,
  refunds, and subscriptions aren't implemented for it; it also
  requires `api_secret`, `merchant_id`, and `service_type_id` in
  addition to `api_key`. It was implemented from Remita's published
  docs but not verified against a live sandbox — double-check field
  names/status codes for your account before relying on it in production.
- PayPal does not support NGN either. Auth is OAuth2 client
  credentials (`api_key` = Client ID, `api_secret` = Client Secret,
  both required); webhook verification needs multiple header values,
  not one signature string — see [docs/guides/providers.md](https://github.com/onwuagba/paystore-py/blob/main/docs/guides/providers.md#paypal).
  Also implemented from docs, not verified against a live account.
- Refunds accept an optional `amount` for a partial refund; omit it to
  refund in full: `gateway.payments.refund(reference, amount=500)`.
- Plan `interval` values are provider-specific and passed straight
  through — Paystack wants `"monthly"`, Stripe wants `"month"`, etc.
- Transfers: Paystack needs a `create_recipient()` step first;
  Flutterwave's `initiate()` takes bank details directly instead.
  Stripe's payout model (Connect) is different enough it isn't wrapped
  here at all.
- Split payments: create a subaccount, then pass its id to
  `initialize()` via a provider-specific kwarg (Paystack's
  `subaccount`, Flutterwave's `subaccounts`) — see
  [docs/guides/providers.md](https://github.com/onwuagba/paystore-py/blob/main/docs/guides/providers.md).
  Stripe's equivalent (a destination charge) already works via
  `initialize(transfer_data=..., application_fee_amount=...)` with no
  new method needed.

## Refunds and recurring billing

```python
# Refund (full or partial)
gateway.payments.refund(transaction["reference"])
gateway.payments.refund(transaction["reference"], amount=500)  # partial

# Recurring billing (Paystack/Stripe — see Provider Support above)
plan = gateway.subscriptions.create_plan(
    name="Monthly", amount=5000, interval="monthly"  # Stripe: interval="month"
)
subscription = gateway.subscriptions.subscribe(
    customer=customer["customer_code"], plan=plan["plan_code"]
)
gateway.subscriptions.cancel(subscription["subscription_code"])
```

## Transfers and split payments

```python
# Transfers/payouts (Paystack/Flutterwave — see Provider Support above)
recipient = gateway.transfers.create_recipient(
    name="Ada Lovelace", account_number="0123456789", bank_code="058"
)
gateway.transfers.initiate(recipient=recipient["recipient_code"], amount=5000)

# Split payments (Paystack/Flutterwave)
subaccount = gateway.subaccounts.create(
    business_name="Vendor Ltd", account_number="0123456789", bank_code="058"
)
gateway.payments.initialize(
    amount=10000, email="customer@example.com", subaccount=subaccount["subaccount_code"]
)
```

## Async usage

`AsyncGateway` wraps `Gateway` for use in FastAPI or async Django views.
It runs calls in a thread pool rather than making native non-blocking
HTTP requests (paystore's providers use a synchronous `httpx.Client`),
so it keeps your event loop unblocked without duplicating every
provider as async:

```python
from paystore import AsyncGateway

gateway = AsyncGateway(provider="paystack", api_key="sk_test_...")

@app.post("/pay")
async def pay():
    transaction = await gateway.initialize_payment(10000, "customer@example.com")
    return {"url": transaction["authorization_url"]}
```

It mirrors `Gateway`'s methods directly (`initialize_payment`,
`verify_payment`, `charge_authorization`, `refund_payment`,
`create_customer`, `get_customer`, `update_customer`, `list_tokens`,
`deactivate_token`, `create_plan`, `subscribe`, `cancel_subscription`,
`verify_webhook`, plus a synchronous `supports()`) rather than the
`.payments`/`.customers`/`.tokens`/`.subscriptions` facade.

## Logging

paystore logs HTTP requests (method, host, and outcome only — never
headers, bodies, or full URLs, since some providers embed credentials
in the URL path) via the standard `logging` module under
`"paystore.http"`. It's silent by default; enable it when debugging:

```python
import logging
logging.getLogger("paystore").setLevel(logging.DEBUG)
logging.basicConfig()
```

## Django

For Django projects, see [paystore-django](https://github.com/onwuagba/paystore-py/tree/main/paystore-django) — a
settings-based `Gateway` factory and a ready-to-subclass webhook view,
shipped as a separate installable package in this repo.

## Documentation

Start at [docs/index.md](https://github.com/onwuagba/paystore-py/blob/main/docs/index.md)
for the full guide index — authentication, provider setup, webhooks,
tokenization, refunds/subscriptions, and async usage.

## Contributing

We use Poetry for dependency management. See [CONTRIBUTING.md](https://github.com/onwuagba/paystore-py/blob/main/CONTRIBUTING.md) for details.

```bash
# Setup development environment
poetry install
poetry run pre-commit install

# Run tests
poetry run pytest

# Update requirements.txt (if needed)
poetry export -f requirements.txt --output requirements.txt --without-hashes
poetry export -f requirements.txt --output requirements-dev.txt --with dev --without-hashes
```

## License

MIT License - see [LICENSE](https://github.com/onwuagba/paystore-py/blob/main/LICENSE)
