# Security Policy

paystore handles payment provider credentials and card-related tokens, so
security issues here can have real financial impact. Please report
responsibly.

## Reporting a Vulnerability

**Do not open a public GitHub issue for security vulnerabilities.**

Instead, email **onwuagbakenenna[at]gmail.com** with:

- A description of the vulnerability and its potential impact
- Steps to reproduce (a minimal repro is very helpful)
- The version of `paystore` (and `paystore-django`, if relevant) affected

You should receive an acknowledgement within 5 business days. We'll work
with you to understand and address the issue, and credit you in the
fix's release notes (unless you'd prefer to stay anonymous).

## Supported Versions

Until a 1.0 release, only the latest published version on PyPI receives
security fixes.

## Scope

In scope:

- The `paystore` core library and the `paystore-django` package in this
  repository.

Out of scope:

- Vulnerabilities in the payment providers' own APIs (Paystack,
  Flutterwave, Stripe, Remita) — report those to the provider directly.
- Issues that require an attacker to already have your API keys or
  webhook secrets.
