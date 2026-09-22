# Paystore Documentation

A unified Python library for integrating multiple payment providers —
switch gateways with a one-line change instead of a rewrite.

## Getting started

- **[Quick Start](quickstart.md)** — install, authenticate, and
  initialize/verify your first payment.
- **[Authentication Guide](guides/authentication.md)** — every way to
  supply credentials (direct, env vars, Django/Flask/FastAPI settings,
  `Config` objects), plus security best practices and deployment
  platform examples.
- **[Provider Reference](guides/providers.md)** — setup, credentials,
  and quirks for each of Paystack, Flutterwave, Stripe, and Remita.

## Features

- **[Webhooks](guides/webhooks.md)** — verifying signatures, where
  each provider's signature header lives, and framework integration
  (Django, or anything else via the stdlib example).
- **[Tokenization](guides/tokenization.md)** — saving cards, listing
  and deactivating them, and charging a saved card later.
- **[Refunds and Recurring Billing](guides/refunds-and-subscriptions.md)**
  — full/partial refunds, native Plan/Subscription objects
  (Paystack/Stripe), and the DIY `charge_authorization`-loop pattern
  for providers that don't have native subscriptions.
- **[Async Usage](guides/async.md)** — `AsyncGateway` for FastAPI and
  async Django views.

## Framework integration

- **Django**: use the separate
  [`paystore-django`](https://github.com/onwuagba/paystore-py/tree/main/paystore-django)
  package (`pip install paystore-django`) — a settings-based `Gateway`
  factory and a ready-to-subclass webhook view.
- **Everything else**: `paystore` itself is framework-agnostic; see
  [`examples/`](https://github.com/onwuagba/paystore-py/tree/main/examples)
  for FastAPI/Flask/stdlib-style usage, including a webhook receiver.

## Reference

- **[CHANGELOG](https://github.com/onwuagba/paystore-py/blob/main/CHANGELOG.md)**
  — what changed in each release.
- **[Provider Support matrix](https://github.com/onwuagba/paystore-py#provider-support)**
  (in the README) — which features each provider implements.
- **[Contributing](https://github.com/onwuagba/paystore-py/blob/main/CONTRIBUTING.md)**
  — dev setup, testing (including the real-sandbox smoke test), and
  the release process.
- **[Security Policy](https://github.com/onwuagba/paystore-py/blob/main/SECURITY.md)**
  — how to report a vulnerability.
