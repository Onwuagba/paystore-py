# Examples

| File | Shows |
|---|---|
| [`basic_usage.py`](basic_usage.py) | Authenticating (direct credentials, env vars, `.env`) and initializing/verifying a payment |
| [`multi_provider_example.py`](multi_provider_example.py) | Initializing a payment with Paystack, Flutterwave, or Stripe using the same code |
| [`tokenization_example.py`](tokenization_example.py) | Creating a customer, listing saved cards, and charging a saved card |
| [`subscription_example.py`](subscription_example.py) | Charging saved cards on a schedule for recurring/subscription billing |
| [`webhook_server_example.py`](webhook_server_example.py) | A minimal (stdlib-only) server that verifies and handles provider webhooks |

Most of these need a sandbox API key — see the [Quick Start](../docs/quickstart.md)
and [Authentication Guide](../docs/guides/authentication.md) for how credentials
are resolved. Django projects should use
[`paystore-django`](../paystore-django/) instead of `webhook_server_example.py`.

Run any of them with:

```bash
poetry run python examples/<file>.py
```
