# Changelog

All notable changes to this project are documented here.
This project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added
- Flutterwave and Stripe providers, so `Gateway(provider=...)` can target
  Paystack, Flutterwave, or Stripe interchangeably.
- Tokenization/customer-management support: `charge_authorization`, customer
  CRUD, and saved-card listing, plus a `TokenManager` helper.
- `Config.webhook_secret` for providers that sign webhooks separately from
  the API key (Stripe, Flutterwave).
- Test coverage for validation, tokenization, webhooks, and all three
  providers (84% overall).

### Fixed
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
