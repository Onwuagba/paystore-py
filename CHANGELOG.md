# Changelog

All notable changes to this project are documented here.
This project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.5.0] - 2026-10-19

### Added
- `Invoice` / `InvoiceStatus` models, `gateway.invoices.list/get` (Stripe),
  and `WebhookEvent.invoice` on invoice.* events (number, amounts,
  hosted/PDF URLs, attempt_count/next_attempt_at for dunning). PayPal and
  Paystack billing events parse into `Invoice` too.
- More neutral event types: `subscription.trial_will_end`, `.paused`,
  `.resumed`, `invoice.created/finalized/upcoming/payment_action_required/
  voided/uncollectible`, `checkout.expired`, `dispute.created`.
- `gateway.subscriptions.capabilities()` — per-provider flags
  (cancel_at_period_end, billing_portal, quantity_change_needs_approval,
  verified_live, ...) so callers can branch without catching errors.
- `Payment` now carries `amount`, `currency`, `customer_id` and
  `subscription_id`, so `gateway.payments.retrieve()` confirms a Stripe
  Checkout Session (including subscription checkouts) without raw dicts.
- `create_plan(product=...)` (Stripe) / `create_plan(product_id=...)`
  (PayPal) to add prices to an existing product; `product_id` is returned.
- `Subscription.approval_url`, set when a PayPal seat change needs the
  customer's approval.

### Changed
- httpx constraint widened from `^0.25.0` to `>=0.25.0,<1.0` (tested on
  0.25.2 and 0.28.1).

## [0.4.0] - 2026-10-19

### Added
- Normalized `Subscription` / `SubscriptionStatus` models (also exported
  from `paystore`) for Stripe, PayPal and Paystack.
- `gateway.subscriptions.get/resume/update/checkout/portal` and
  `cancel(at_period_end=True)`.
- Stripe: cancel at period end, resume, seat quantity, trial days,
  automatic tax, hosted subscription Checkout and billing portal.
- PayPal Subscriptions: `create_plan` (trials, tax), approval-link
  subscribe, get/cancel/resume/revise quantity. Unverified against a
  live account.
- `WebhookEvent.type` (neutral event name), `.id`, `.created_at` and
  `.subscription`; PayPal events are now parsed.
- `paystore.webhooks.headers.build_signature()` (handles PayPal's
  five-header signature).
- `Payment` / `PaymentStatus` models and `gateway.payments.retrieve()`
  (typed counterpart of `verify`).

### Changed
- Development status classifier raised from Alpha to Beta. PayPal, Remita
  and MoMo remain unverified against live accounts.

## [0.3.0] - 2026-09-22

### Added
- PayPal provider: OAuth2 client-credentials auth, Orders v2 for
  initialize/verify (auto-captures approved orders), refunds, and
  webhook signature verification (via PayPal's own verify API — see
  [docs/guides/providers.md](https://github.com/onwuagba/paystore-py/blob/main/docs/guides/providers.md#paypal)
  for the multi-header signature shape it needs).
- MTN Mobile Money (MoMo) provider: Collections API integration —
  `initialize_payment` sends a Request to Pay prompt to the payer's
  phone and returns immediately as `"pending"`; poll `verify_payment`
  for the result. No saved-payment-method or webhook-signing support
  (documented as intentionally unimplemented, not a gap — see
  [docs/guides/providers.md](https://github.com/onwuagba/paystore-py/blob/main/docs/guides/providers.md#mtn-mobile-money-momo)).
- `paystore.utils.currency.to_decimal_string()` — converts minor-unit
  int amounts to the decimal-string format PayPal/MoMo expect.
- `Gateway.transfers` / `AsyncGateway`: transfer/payout support for
  Paystack and Flutterwave (`create_recipient`, `initiate`).
- `Gateway.subaccounts`: split-payment subaccount creation for
  Paystack and Flutterwave.
- `paystore.webhooks.events.WebhookEvent` and
  `Gateway.parse_webhook_event()` / `AsyncGateway.parse_webhook_event()`
  — a typed, normalized webhook event shape instead of raw
  provider-specific payloads.
- `HTTPClient` now respects a `Retry-After` header on 429 responses
  (capped at 30s) instead of always using exponential backoff.
- `paystore-django`: `PaystoreAsyncWebhookView` for async Django
  views, and `DjangoORMStorage` — a `BaseStorage` implementation that
  persists transactions to a `PaystoreTransaction` model.
- GitHub Pages documentation site, built from `/docs`:
  https://onwuagba.github.io/paystore-py/

### Fixed
- `HTTPClient` no longer crashes on a 2xx response with an empty body
  (e.g. MoMo's `requesttopay` 202 response) — returns `{}` instead of
  failing on `response.json()`.

## [0.2.1] - 2026-09-22

### Fixed
- README links (docs, CONTRIBUTING.md, LICENSE, paystore-django) were
  relative paths that work fine on GitHub but rendered dead on the
  PyPI project page, since PyPI has no base URL to resolve them
  against. Converted to absolute `github.com/onwuagba/paystore-py/...`
  URLs.

## [0.2.0] - 2026-09-22

### Added
- Flutterwave, Stripe, and Remita providers, so `Gateway(provider=...)` can
  target Paystack, Flutterwave, Stripe, or Remita interchangeably.
- `Config.api_secret`/`merchant_id`/`service_type_id` for Remita's RRR-based
  auth scheme (a single `api_key` isn't enough for it).
- `Gateway.verify_webhook()` convenience method.
- `paystore-django`: a separate installable package (in this repo) with a
  settings-based `Gateway` factory and a webhook view for Django projects.
- Tokenization/customer-management support: `charge_authorization`, customer
  CRUD, and saved-card listing, plus a `TokenManager` helper.
- `Config.webhook_secret` for providers that sign webhooks separately from
  the API key (Stripe, Flutterwave).
- Test coverage for validation, tokenization, webhooks, and all three
  providers (84% overall).
- `Gateway.payments.initialize`/`create`/`charge_authorization` now
  validate email/amount input, persist results through an optional
  pluggable `storage` backend, and support an `idempotency_key` on
  `charge_authorization` to dedupe retries (protects against
  double-charging, e.g. a cron job re-running after a network blip).
- `AuthenticationError`, `RateLimitError`, `NetworkError` exception
  subclasses, so callers can distinguish retryable failures from
  permanent ones instead of catching one generic `ProviderError`.
  `HTTPClient` now retries transient GET failures (429/5xx/network)
  with backoff; POSTs are never auto-retried without an idempotency
  guarantee.
- `paystore/py.typed` (PEP 561) so downstream mypy users get type
  checking, and `SECURITY.md` with a vulnerability-disclosure policy.
- `AsyncGateway`: a thread-pool-backed async wrapper around `Gateway` for
  FastAPI/async Django, without a full async rewrite of every provider.
- `validate_amount` now rejects non-`int` amounts (e.g. `10.50`), which
  previously would have been silently sent to the provider as-is.
- Request logging under the `"paystore.http"` logger (method/host/
  outcome only, silent by default) via the standard `logging` module.
- `Config.__repr__`/`__str__` now mask `api_key`/`api_secret`/
  `webhook_secret` so printing or logging a `Config` doesn't leak them.
- `Gateway.supports(feature)` to check whether the active provider
  implements an optional feature (`"charge_authorization"`,
  `"customers"`, `"tokens"`) instead of catching `NotImplementedError`.
- `examples/webhook_server_example.py`: a stdlib-only webhook receiver
  for non-Django usage (paystore-django already had one for Django).
- `scripts/smoke_test.py`: an opt-in script that hits real provider
  sandboxes to catch anything mocked tests can't (see CONTRIBUTING.md).
- Refunds: `gateway.payments.refund(reference, amount=None)` (full or
  partial), implemented for Paystack, Flutterwave, and Stripe.
- Recurring billing: `gateway.subscriptions.create_plan`/`subscribe`/
  `cancel`, wrapping each provider's native Plan/Subscription objects
  (Paystack and Stripe only — see Provider Support in the README for
  why Flutterwave/Remita aren't included).
- `HTTPClient.delete()` (needed for Stripe subscription cancellation).
- `paystore.utils.currency.is_zero_decimal_currency` — Stripe requires
  *not* multiplying JPY/KRW-style currencies by 100.
- `paystore.webhooks.headers.SIGNATURE_HEADERS`: the provider-name to
  signature-header mapping, shared by paystore-django and
  `examples/webhook_server_example.py` instead of being duplicated.

### Fixed
- `HTTPClient` exceptions now suppress the original httpx exception as
  their cause (`raise ... from None`), since httpx's default
  `HTTPStatusError` message embeds the full request URL and Remita
  embeds its API key/hash directly in that URL — without this, a
  routine traceback could print a Remita API key in plaintext.
- `validate_email` rejected almost all real addresses due to a literal
  `{{2,}}` in its regex instead of the `{2,}` quantifier.
- Several error messages across the codebase were missing their `f` prefix,
  so they printed the literal `{variable}` text instead of the interpolated
  value.
- `generate_reference` produced the literal string
  `"{prefix}_{random_part}"` instead of a real unique reference.

## [0.1.0] - 2026-09-19

Initial release: Paystack provider, core Gateway/Config/HTTPClient, webhook
verification, and input validation.
