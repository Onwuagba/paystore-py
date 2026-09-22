# Provider Reference

Detailed setup and quirks per provider. For the at-a-glance feature
matrix, see the [README](https://github.com/onwuagba/paystore-py#provider-support).

## Paystack

```python
gateway = Gateway(provider="paystack", api_key="sk_test_...")
```

- Env var: `PAYSTACK_SECRET_KEY` (or `PAYSTACK_API_KEY`).
- Currency: NGN by default; supports whatever currencies your Paystack
  account is enabled for.
- Webhooks are signed with your `api_key` — no separate
  `webhook_secret` needed.
- Full feature support: `charge_authorization`, `customers`, `tokens`,
  `refunds`, `subscriptions`.

## Flutterwave

```python
gateway = Gateway(
    provider="flutterwave",
    api_key="FLWSECK_TEST-...",
    webhook_secret="...",  # the "secret hash" from your dashboard's webhook settings
)
```

- Env vars: `FLUTTERWAVE_SECRET_KEY`, `FLUTTERWAVE_WEBHOOK_SECRET`.
- Webhooks: Flutterwave doesn't cryptographically sign payloads — it
  sends the `verif-hash` header set to a secret string you configure
  in the dashboard, which must match `webhook_secret` exactly.
  `webhook_secret` is **required** to verify webhooks (raises
  `ConfigurationError` if missing).
- Supports `charge_authorization` and `refunds`. Does **not** support
  `customers`/`tokens` (no first-class saved-customer API) or
  `subscriptions` via `gateway.subscriptions` — see
  [refunds-and-subscriptions.md](refunds-and-subscriptions.md) for its
  `payment_plan` alternative.
- Refunds resolve your `reference` (tx_ref) to Flutterwave's internal
  numeric transaction id first (one extra API call) — happens
  automatically inside `gateway.payments.refund(...)`.

## Stripe

```python
gateway = Gateway(
    provider="stripe",
    api_key="sk_test_...",
    webhook_secret="whsec_...",
)
```

- Env vars: `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`.
- **Does not support NGN.** Pass a currency Stripe supports, e.g.
  `currency="USD"`.
- Zero-decimal currencies (JPY, KRW, etc.) must **not** be multiplied
  by 100 — see `paystore.utils.currency.is_zero_decimal_currency`.
- `initialize_payment` creates a Checkout Session; the returned
  `reference` is the session id (`cs_...`). `charge_authorization`
  creates a PaymentIntent directly; its `reference` is `pi_...`.
  `gateway.payments.refund(reference)` accepts either.
- `idempotency_key` on `charge_authorization` is sent as Stripe's
  native `Idempotency-Key` header, in addition to paystore's own
  client-side dedup — safe across process restarts, not just within
  one `Gateway` instance.
- Full feature support: `charge_authorization`, `customers`, `tokens`,
  `refunds`, `subscriptions` (via Product + recurring Price +
  Subscription objects under the hood).

## Remita

```python
gateway = Gateway(
    provider="remita",
    api_key="...",
    api_secret="...",       # required — Remita's request-signing secret
    merchant_id="...",      # required
    service_type_id="...",  # required
)
```

- Env var for `api_key`: `REMITA_SECRET_KEY`. `api_secret`,
  `merchant_id`, and `service_type_id` have no env var auto-resolution
  — pass them explicitly (see
  [authentication.md](authentication.md#remitas-extra-credentials)).
- Uses an RRR (Remita Retrieval Reference) flow: `initialize_payment`
  generates an RRR and returns a hosted payment URL; `verify_payment`
  takes that RRR as `reference`.
- Only `initialize_payment`, `verify_payment`, and webhook
  verification are implemented. `charge_authorization`, `customers`,
  `refunds`, and `subscriptions` all raise `NotImplementedError` — no
  clean equivalent in Remita's collections API.
- ⚠️ Implemented from Remita's published docs but **not verified
  against a live sandbox** (Remita has shipped several API variants
  over the years — RIMS, cREST, e-commerce). Run
  [`scripts/smoke_test.py`](https://github.com/onwuagba/paystore-py/blob/main/scripts/smoke_test.py)
  against your own sandbox account before relying on this in
  production, and double-check field names/status codes if something
  doesn't match.

## PayPal

```python
gateway = Gateway(
    provider="paypal",
    api_key="...",         # the app's Client ID
    api_secret="...",      # required — the app's Client Secret
    webhook_secret="...",  # required for webhooks — the Webhook ID, not a signing secret
)
```

- Env var for `api_key`: `PAYPAL_SECRET_KEY`. `api_secret` has no env
  var auto-resolution — pass it explicitly.
- **Does not support NGN.** Pass a currency PayPal supports, e.g.
  `currency="USD"`.
- Auth is OAuth2 client credentials, not a static Bearer key — an
  access token is fetched and cached automatically, refreshed shortly
  before it expires. Amounts are decimal strings in PayPal's API
  ("10.00"); still pass minor-unit ints here (1000) like every other
  provider — converted internally (zero-decimal currencies excepted,
  same as Stripe).
- `initialize_payment` creates an Order the customer must approve —
  `verify_payment` captures it automatically if it's `APPROVED`.
  PayPal payments don't complete on their own the way the other
  providers' do.
- `refund_payment` resolves your Order `reference` to its capture id
  first (one extra API call).
- Only `initialize_payment`, `verify_payment`, `refund_payment`, and
  webhook verification are implemented — PayPal's saved-payment-method
  product (Vault) is a separate, more involved API not covered here.
- Webhook verification needs **multiple** header values, not one
  signature string like every other provider — see
  [webhooks.md](webhooks.md) and the provider's own docstring for the
  exact shape to pass as `signature`.
- ⚠️ Implemented from PayPal's published Orders v2/Webhooks docs, not
  verified against a live account — same caveat as Remita.
