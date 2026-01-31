# Quick Start

## Installation

```bash
pip install paystore
```

## Authentication Methods

### Method 1: Direct Credentials (Simplest)

```python
from paystore import Gateway

gateway = Gateway(
    provider="paystack",
    api_key="sk_test_your_secret_key",
    environment="sandbox"
)
```

### Method 2: Environment Variables (Recommended for Production)

```bash
# In your .env file or environment
export PAYSTACK_SECRET_KEY=sk_test_your_secret_key
export PAYMENT_ENVIRONMENT=sandbox
```

```python
from paystore import Gateway

# API key loaded automatically from PAYSTACK_SECRET_KEY
gateway = Gateway(provider="paystack")
```

### Method 3: From Django Settings

```python
# settings.py
PAYMENT_PROVIDER = "paystack"
PAYSTACK_SECRET_KEY = env('PAYSTACK_SECRET_KEY')

# views.py
from django.conf import settings
from paystore import Gateway

gateway = Gateway(
    provider=settings.PAYMENT_PROVIDER,
    api_key=settings.PAYSTACK_SECRET_KEY
)
```

### Method 4: From Flask Config

```python
# config.py
class Config:
    PAYMENT_PROVIDER = os.getenv('PAYMENT_PROVIDER', 'paystack')
    PAYSTACK_SECRET_KEY = os.getenv('PAYSTACK_SECRET_KEY')

# app.py
from paystore import Gateway

gateway = Gateway(
    provider=app.config['PAYMENT_PROVIDER'],
    api_key=app.config['PAYSTACK_SECRET_KEY']
)
```

## Basic Usage

```python
# Initialize payment
transaction = gateway.payments.initialize(
    amount=10000,  # ₦100.00 (in kobo)
    email="customer@example.com",
    currency="NGN"
)

print(f"Payment URL: {transaction['authorization_url']}")
print(f"Reference: {transaction['reference']}")

# Verify payment (after customer completes payment)
result = gateway.payments.verify(transaction['reference'])

if result['status'] == 'success':
    print(f"Payment successful! Amount: {result['amount']}")
```

## Next Steps

- [Authentication Guide](guides/authentication.md) - Detailed authentication methods
- [Security Best Practices](guides/security.md) - Keep your credentials safe
