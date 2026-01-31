# Authentication Guide

This guide explains all the ways developers can authenticate with the payment library.

## Overview

The library supports multiple authentication methods to fit different use cases:

1. **Direct credentials** - Simple, good for testing
2. **Environment variables** - Recommended for production
3. **Framework integration** - Django, Flask, FastAPI
4. **Config objects** - Advanced use cases

## Method 1: Direct Credentials

### When to Use
- Quick prototyping
- Testing
- Scripts and CLI tools

### Example

```python
from paystore import Gateway

gateway = Gateway(
    provider="paystack",
    api_key="sk_test_abc123",
    environment="sandbox"
)
```

### ⚠️ Warning
Never hardcode production keys in source code!

---

## Method 2: Environment Variables (Recommended)

### When to Use
- Production applications
- When deploying to cloud platforms
- CI/CD pipelines
- Following 12-factor app principles

### Setup

**Option A: .env file (local development)**

```bash
# .env
PAYSTACK_SECRET_KEY=sk_test_abc123
FLUTTERWAVE_SECRET_KEY=FLWSECK_TEST-xyz789
PAYMENT_ENVIRONMENT=sandbox
```

```python
from paystore import Gateway
from dotenv import load_dotenv

load_dotenv()  # Load .env file

# API key automatically loaded from PAYSTACK_SECRET_KEY
gateway = Gateway(provider="paystack")
```

**Option B: System environment (production)**

```bash
# On your server or in Docker
export PAYSTACK_SECRET_KEY=sk_live_real_key
export PAYMENT_ENVIRONMENT=production
```

```python
from paystore import Gateway

# Credentials loaded from environment
gateway = Gateway(provider="paystack")
```

### Environment Variable Naming

The library checks these variables in order:

1. `{PROVIDER}_SECRET_KEY` (e.g., `PAYSTACK_SECRET_KEY`)
2. `{PROVIDER}_API_KEY` (e.g., `PAYSTACK_API_KEY`)
3. `PAYMENT_API_KEY` (generic fallback)

---

## Method 3: Django Integration

### settings.py

```python
# settings.py
import os
from pathlib import Path
from environs import Env

env = Env()
env.read_env()

# Payment Configuration
PAYMENT_PROVIDER = env.str('PAYMENT_PROVIDER', 'paystack')
PAYMENT_ENVIRONMENT = env.str('PAYMENT_ENVIRONMENT', 'sandbox')

# Provider Keys
PAYSTACK_SECRET_KEY = env.str('PAYSTACK_SECRET_KEY', '')
FLUTTERWAVE_SECRET_KEY = env.str('FLUTTERWAVE_SECRET_KEY', '')
STRIPE_SECRET_KEY = env.str('STRIPE_SECRET_KEY', '')
```

### views.py

```python
from django.conf import settings
from paystore import Gateway

def initialize_payment(request):
    # Method A: From settings
    gateway = Gateway(
        provider=settings.PAYMENT_PROVIDER,
        api_key=settings.PAYSTACK_SECRET_KEY,
        environment=settings.PAYMENT_ENVIRONMENT
    )
    
    # Method B: Auto-detect from environment
    gateway = Gateway(provider="paystack")  # Uses PAYSTACK_SECRET_KEY
    
    transaction = gateway.payments.initialize(
        amount=10000,
        email=request.user.email
    )
    
    return redirect(transaction['authorization_url'])
```

### Create a Gateway Service (Recommended)

```python
# payments/services.py
from django.conf import settings
from paystore import Gateway

class PaymentService:
    _gateway = None
    
    @classmethod
    def get_gateway(cls):
        if cls._gateway is None:
            cls._gateway = Gateway(
                provider=settings.PAYMENT_PROVIDER,
                api_key=getattr(settings, f'{settings.PAYMENT_PROVIDER.upper()}_SECRET_KEY'),
                environment=settings.PAYMENT_ENVIRONMENT
            )
        return cls._gateway

# Usage in views
from .services import PaymentService

def process_payment(request):
    gateway = PaymentService.get_gateway()
    transaction = gateway.payments.initialize(...)
```

---

## Method 4: Flask Integration

### config.py

```python
import os

class Config:
    # Payment Configuration
    PAYMENT_PROVIDER = os.getenv('PAYMENT_PROVIDER', 'paystack')
    PAYMENT_ENVIRONMENT = os.getenv('PAYMENT_ENVIRONMENT', 'sandbox')
    
    PAYSTACK_SECRET_KEY = os.getenv('PAYSTACK_SECRET_KEY')
    FLUTTERWAVE_SECRET_KEY = os.getenv('FLUTTERWAVE_SECRET_KEY')

class DevelopmentConfig(Config):
    DEBUG = True
    PAYMENT_ENVIRONMENT = 'sandbox'

class ProductionConfig(Config):
    DEBUG = False
    PAYMENT_ENVIRONMENT = 'production'
```

### app.py

```python
from flask import Flask, current_app
from paystore import Gateway

app = Flask(__name__)
app.config.from_object('config.DevelopmentConfig')

# Method A: Create gateway instance
def get_gateway():
    return Gateway(
        provider=current_app.config['PAYMENT_PROVIDER'],
        api_key=current_app.config['PAYSTACK_SECRET_KEY'],
        environment=current_app.config['PAYMENT_ENVIRONMENT']
    )

# Method B: Flask extension pattern (advanced)
class PaymentGateway:
    def __init__(self, app=None):
        self.app = app
        if app:
            self.init_app(app)
    
    def init_app(self, app):
        app.extensions = getattr(app, 'extensions', {})
        app.extensions['payment_gateway'] = Gateway(
            provider=app.config['PAYMENT_PROVIDER'],
            api_key=app.config['PAYSTACK_SECRET_KEY'],
            environment=app.config['PAYMENT_ENVIRONMENT']
        )

# Initialize extension
payment = PaymentGateway(app)

# Usage in routes
@app.route('/pay')
def initiate_payment():
    gateway = current_app.extensions['payment_gateway']
    transaction = gateway.payments.initialize(...)
```

---

## Method 5: FastAPI Integration

```python
from fastapi import FastAPI, Depends
from pydantic import BaseSettings
from paystore import Gateway

class Settings(BaseSettings):
    payment_provider: str = "paystack"
    paystack_secret_key: str
    payment_environment: str = "sandbox"
    
    class Config:
        env_file = ".env"

settings = Settings()

# Dependency injection
def get_gateway():
    return Gateway(
        provider=settings.payment_provider,
        api_key=settings.paystack_secret_key,
        environment=settings.payment_environment
    )

app = FastAPI()

@app.post("/payments/initialize")
async def initialize_payment(
    email: str,
    amount: int,
    gateway: Gateway = Depends(get_gateway)
):
    transaction = gateway.payments.initialize(
        amount=amount,
        email=email
    )
    return transaction
```

---

## Method 6: Config Object (Advanced)

For complex configurations or multiple gateways:

```python
from paystore import Gateway
from paystore.core.config import Config

# Create config objects
paystack_config = Config(
    provider="paystack",
    api_key="sk_test_paystack_key",
    environment="sandbox",
    timeout=30,
    max_retries=3
)

flutterwave_config = Config(
    provider="flutterwave",
    api_key="FLWSECK_TEST-key",
    environment="sandbox"
)

# Use configs
paystack_gateway = Gateway(config=paystack_config)
flutterwave_gateway = Gateway(config=flutterwave_config)

# Use based on condition
def get_gateway_for_currency(currency):
    if currency == "NGN":
        return Gateway(config=paystack_config)
    else:
        return Gateway(config=flutterwave_config)
```

---

## Security Best Practices

### ✅ DO

- **Use environment variables in production**
- **Use .env files for local development** (add to .gitignore!)
- **Use framework config systems** (Django settings, Flask config)
- **Rotate keys regularly**
- **Use different keys for sandbox/production**
- **Store keys in secret managers** (AWS Secrets Manager, HashiCorp Vault)

### ❌ DON'T

- **Never commit keys to Git**
- **Never hardcode production keys**
- **Never expose keys in client-side code**
- **Never log API keys**
- **Never share keys via email/chat**

---

## Deployment Platforms

### Heroku

```bash
heroku config:set PAYSTACK_SECRET_KEY=sk_live_xxx
heroku config:set PAYMENT_ENVIRONMENT=production
```

### AWS (using environment variables)

```bash
# In your Elastic Beanstalk config
aws elasticbeanstalk set-environment   -e PAYSTACK_SECRET_KEY=sk_live_xxx   -e PAYMENT_ENVIRONMENT=production
```

### Docker

```yaml
# docker-compose.yml
services:
  web:
    environment:
      - PAYSTACK_SECRET_KEY=${PAYSTACK_SECRET_KEY}
      - PAYMENT_ENVIRONMENT=production
    env_file:
      - .env
```

### Kubernetes

```yaml
# secret.yaml
apiVersion: v1
kind: Secret
metadata:
  name: payment-secrets
type: Opaque
data:
  paystack-secret-key: <base64-encoded-key>
```

---

## Troubleshooting

### Error: "API key not provided"

**Cause**: Gateway couldn't find credentials

**Solutions**:
1. Pass `api_key` directly
2. Set `PAYSTACK_SECRET_KEY` environment variable
3. Check variable naming (must be `{PROVIDER}_SECRET_KEY`)

### Error: "Invalid API key"

**Cause**: Wrong key for environment

**Solutions**:
1. Verify you're using the correct key (test vs live)
2. Check `environment` parameter matches key type
3. Ensure no extra spaces in key

### Keys not loading from .env

**Solutions**:
```python
from dotenv import load_dotenv
load_dotenv()  # Add this before importing Gateway
```

---

## Summary

| Method | Best For | Example |
|--------|----------|---------|
| Direct | Testing, prototypes | `Gateway(api_key="sk_...")` |
| Environment Variables | Production | `Gateway(provider="paystack")` |
| Django Settings | Django apps | `Gateway(api_key=settings.KEY)` |
| Flask Config | Flask apps | `Gateway(api_key=app.config['KEY'])` |
| FastAPI Settings | FastAPI apps | `Settings().paystack_key` |
| Config Object | Advanced/multi-gateway | `Gateway(config=config_obj)` |

**Recommended**: Use environment variables with framework config systems for the best security and flexibility.
