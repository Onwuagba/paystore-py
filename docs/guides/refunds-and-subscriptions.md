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

### Option 1: Native plans/subscriptions (Paystack, Stripe)

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

`interval` is passed straight through to the provider, unmodified —
values are provider-specific:

| Provider | Valid `interval` values |
|---|---|
| Paystack | `"hourly"`, `"daily"`, `"weekly"`, `"monthly"`, `"quarterly"`, `"biannually"`, `"annually"` |
| Stripe | `"day"`, `"week"`, `"month"`, `"year"` |

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
