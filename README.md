# Paystore

A unified Python library for integrating multiple payment providers, so
switching gateways is a one-line change instead of a rewrite.

## Features

- Multi-provider support: Paystack, Flutterwave, Stripe
- Swap providers by changing one string — `initialize`/`verify`/
  `charge_authorization` return a consistent shape (`reference`,
  `authorization_url`, `status`) across all of them
- Saved cards / recurring charges via `charge_authorization` and
  customer management (Paystack and Stripe; see
  [provider support](#provider-support))
- Webhook signature verification per provider
- Credentials resolved from explicit args, env vars, or framework
  settings (see [docs/guides/authentication.md](docs/guides/authentication.md))

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
git clone https://github.com/onwuagba/paystore.git
cd paystore

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
```

## Provider Support

| Capability | Paystack | Flutterwave | Stripe |
|---|---|---|---|
| Initialize / verify payment | ✅ | ✅ | ✅ |
| Charge saved card (`charge_authorization`) | ✅ | ✅ | ✅ |
| Webhook signature verification | ✅ | ✅ | ✅ |
| Customer management (`gateway.customers`) | ✅ | ❌ | ✅ |
| List/deactivate saved cards (`gateway.tokens`) | ✅ | ❌ | ✅ |

Flutterwave has no first-class "saved customer" API comparable to
Paystack's or Stripe's, so `gateway.customers` and `gateway.tokens`
raise `NotImplementedError` for that provider; recurring charges still
work via `charge_authorization` using the card token from a verified
transaction. Stripe does not support NGN — pass a currency it supports
(e.g. `currency="USD"`).

## Documentation

See the [docs](docs/) directory for full documentation.

## Contributing

We use Poetry for dependency management. See [CONTRIBUTING.md](CONTRIBUTING.md) for details.

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

MIT License - see LICENSE file
