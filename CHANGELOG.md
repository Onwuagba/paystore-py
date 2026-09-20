# Changelog

All notable changes to this project are documented here.
This project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

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
