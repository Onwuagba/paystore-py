# Refunds and Recurring Billing

Provider support for both varies — check
[Provider Support](providers.md) or call `gateway.supports(...)`
before assuming a feature exists.

## Refunds

```python
# Full refund
gateway.payments.refund(transaction["reference"])

# Partial refund (smallest currency unit, e.g. kobo/cents)
gateway.payments.refund(transaction["reference"], amount=500)
```

Works with a reference from either `initialize` or
`charge_authorization`. Supported by Paystack, Flutterwave, and
Stripe — not Remita (its collections API has no equivalent).

```python
if gateway.supports("refunds"):
    gateway.payments.refund(reference)
else:
    raise RuntimeError(f"{gateway.config.provider} doesn't support refunds")
```

## Recurring billing

Two options, depending on how much you want the provider to manage
for you:

### Option 1: Native plans/subscriptions (Paystack, Stripe, PayPal)

Wraps the provider's own Plan/Subscription objects, so retries,
dunning, and proration are handled by the provider, not your code:

```python
plan = gateway.subscriptions.create_plan(
    name="Monthly",
    amount=5000,
    interval="monthly",  # Stripe wants "month" instead — see note below
)

subscription = gateway.subscriptions.subscribe(
    customer=customer["customer_code"],  # or Stripe customer id
    plan=plan["plan_code"],
)

gateway.subscriptions.cancel(subscription["subscription_code"])
```

#### Managing a subscription

`get`, `resume` and `update` return a normalized `Subscription`
(`status` is a `SubscriptionStatus`: `trialing`, `active`, `past_due`,
`unpaid`, `paused`, `incomplete`, `canceled`, `expired`; the provider's
own object is in `.raw`):

```python
sub = gateway.subscriptions.get("sub_123")
if sub.status.value == "past_due": ...

gateway.subscriptions.cancel("sub_123", at_period_end=True)  # keep access until paid period ends
gateway.subscriptions.resume("sub_123")                      # undo it before then
gateway.subscriptions.update("sub_123", quantity=10)         # seats
```

Hosted signup (collects the payment method for you) and the customer
billing portal:

```python
session = gateway.subscriptions.checkout(
    plan="price_123", email="a@example.com", quantity=5,
    trial_days=14, automatic_tax=True,       # Stripe
    success_url="https://app/ok", cancel_url="https://app/no",
)
redirect(session["authorization_url"])

portal = gateway.subscriptions.portal(customer="cus_123", return_url="https://app/account")
redirect(portal["url"])                      # Stripe only
```

| | Stripe | PayPal ⚠️ | Paystack |
|---|---|---|---|
| `get` | ✅ | ✅ | ✅ |
| `cancel(at_period_end=True)` | ✅ | ❌ raises | ✅ (always) |
| `resume` | ✅ undo pending cancel | ✅ reactivate suspended | ❌ |
| `update(quantity=)` | ✅ | ✅ (needs `quantity_supported` plan; may need re-approval) | ❌ |
| `checkout` | ✅ Checkout `mode=subscription` | ✅ approval link | ❌ |
| `portal` | ✅ | ❌ | ❌ |
| Trials | `trial_days` | `create_plan(trial_days=)` | via plan |
| Tax | `automatic_tax=True` | `create_plan(tax_percentage=)` | ❌ |

Check `gateway.subscriptions.capabilities()` instead of hardcoding the
table above — it returns flags such as `cancel_at_period_end`,
`billing_portal`, `quantity_change_needs_approval` (the change returns a
`Subscription.approval_url` to send the buyer to), `fixed_tax_rate` vs
`automatic_tax`, `reuse_product` and `verified_live`.

One product, many prices: `create_plan(..., product=product_id)` (Stripe)
or `product_id=` (PayPal) adds a price to an existing product; reuse the
`product_id` from the first call.

Invoice history (Stripe): `gateway.invoices.list(customer=..., limit=...)`
returns `Invoice` objects with `number`, `amount_due`, `currency`,
`hosted_url`, `pdf_url`, `attempt_count` and `next_attempt_at`. The same
`Invoice` arrives on `event.invoice` for `invoice.*` webhooks.

Confirming a checkout on return: `gateway.payments.retrieve(session_id)`
returns a `Payment` with `status`, `amount`, `currency`, `customer_id` and
`subscription_id`.

PayPal Subscriptions were written from PayPal's docs and are **not
verified against a live account**. PayPal subscriptions are approved by
the customer at PayPal, so `subscribe` returns an `authorization_url`
and the subscription stays `incomplete` until they approve.

`interval` is passed straight through to the provider, unmodified —
values are provider-specific:

| Provider | Valid `interval` values |
|---|---|
| Paystack | `"hourly"`, `"daily"`, `"weekly"`, `"monthly"`, `"quarterly"`, `"biannually"`, `"annually"` |
| Stripe | `"day"`, `"week"`, `"month"`, `"year"` |
| PayPal | `"day"`, `"week"`, `"month"`, `"year"` |

Flutterwave and Remita don't implement `gateway.subscriptions` —
Flutterwave's model attaches a `payment_plan` directly to
`initialize_payment` instead of exposing a separate per-customer
subscribe/cancel API (see below); Remita has no equivalent at all.

### Option 2: DIY charge_authorization loop (every provider that supports charge_authorization)

Works everywhere `charge_authorization` does (Paystack, Flutterwave,
Stripe), at the cost of handling retries/cancellation yourself — e.g.
a cron job that re-charges a saved card on each billing cycle:

```python
result = gateway.payments.charge_authorization(
    authorization_code=saved_card_token,
    email=customer_email,
    amount=9900,
    idempotency_key=f"sub-{subscription_id}-{billing_period}",
)
```

Always pass `idempotency_key` here — without it, a cron job that
retries after a network blip (or runs twice due to a scheduler quirk)
can double-charge the customer. See
[async.md](async.md) if this cron job needs to run inside an async
app without blocking the event loop.

### Flutterwave's Payment Plans

Flutterwave attaches recurring billing to the initial payment itself,
rather than exposing a `create_plan`/`subscribe`/`cancel` API the way
Paystack/Stripe do (so `gateway.subscriptions` raises
`NotImplementedError` for it). Create the payment plan directly via
Flutterwave's dashboard or API, then reference its id:

```python
transaction = gateway.payments.initialize(
    amount=5000, email=customer_email, payment_plan="<flutterwave_plan_id>"
)
```

The customer's first payment enrolls them; Flutterwave auto-charges
subsequent cycles using the saved card, with no separate subscribe
call. There's no per-customer cancel — cancelling a plan (via
Flutterwave's dashboard or API directly) stops it for everyone on it.
