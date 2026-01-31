# Paystore

A unified Python library for integrating multiple payment providers.

## Features

- Multiple provider support (Paystack, Flutterwave, Stripe, etc.)
- Easy provider switching
- Built-in security features
- Comprehensive testing tools

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
```

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
