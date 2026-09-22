# paystore-django

Django integration for [paystore](https://github.com/onwuagba/paystore-py):
a settings-based `Gateway` factory and a ready-to-subclass webhook view.

## Installation

```bash
pip install paystore-django
```

## Settings

```python
# settings.py
PAYSTORE = {
    "PROVIDER": "paystack",
    "ENVIRONMENT": "production",
    # Optional — omit to fall back to paystore's own env var resolution
    # (e.g. PAYSTACK_SECRET_KEY):
    "API_KEY": env("PAYSTACK_SECRET_KEY"),
    "WEBHOOK_SECRET": env("PAYSTACK_WEBHOOK_SECRET"),
    # Provider-specific extras (e.g. Remita's merchant_id/service_type_id/
    # api_secret) go here:
    "EXTRA": {},
}
```

## Usage

```python
from paystore_django import get_gateway

def checkout(request):
    gateway = get_gateway()
    transaction = gateway.payments.initialize(
        amount=10000, email=request.user.email
    )
    return redirect(transaction["authorization_url"])
```

## Webhooks

Subclass `PaystoreWebhookView` and override `handle_event`:

```python
# views.py
from paystore_django import PaystoreWebhookView

class PaystackWebhookView(PaystoreWebhookView):
    provider = "paystack"

    def handle_event(self, event, request):
        if event.get("event") == "charge.success":
            reference = event["data"]["reference"]
            # mark the matching order as paid
```

```python
# urls.py
from django.urls import path
from .views import PaystackWebhookView

urlpatterns = [
    path("webhooks/paystack/", PaystackWebhookView.as_view()),
]
```

The view verifies the provider's signature before calling `handle_event`
(returning `400` if it doesn't match) and also sends a `webhook_verified`
Django signal, if you'd rather listen for it instead of subclassing:

```python
from django.dispatch import receiver
from paystore_django.signals import webhook_verified

@receiver(webhook_verified)
def on_webhook(sender, provider, event, **kwargs):
    ...
```

### Async

`PaystoreAsyncWebhookView` is the same thing backed by `AsyncGateway`,
for Django's async views (`async def post`, ASGI deployment).
`handle_event` may be `async def` or a plain function — both work:

```python
from paystore_django import PaystoreAsyncWebhookView

class PaystackWebhookView(PaystoreAsyncWebhookView):
    provider = "paystack"

    async def handle_event(self, event, request):
        await Order.objects.filter(reference=event["data"]["reference"]).aupdate(paid=True)
```

`get_async_gateway()` is also available directly, mirroring `get_gateway()`.

## Persisting transactions

By default nothing is saved anywhere — `Gateway` uses a no-op storage
backend unless you give it one. `DjangoORMStorage` saves every
transaction result (from `initialize`/`verify`/`charge_authorization`/
`refund`) to a `PaystoreTransaction` row, upserted by `reference`:

```python
# settings.py
INSTALLED_APPS = [
    ...,
    "paystore_django",
]
```

```bash
python manage.py migrate
```

```python
from paystore_django import get_gateway, DjangoORMStorage

def checkout(request):
    gateway = get_gateway(storage=DjangoORMStorage())
    transaction = gateway.payments.initialize(
        amount=10000, email=request.user.email
    )
    return redirect(transaction["authorization_url"])
```

`get_async_gateway(storage=DjangoORMStorage())` works the same way.
Prefer your own storage? Subclass `paystore.storage.base.BaseStorage`
and pass an instance of that instead — `DjangoORMStorage` is one
implementation, not a requirement.

## Development

This package lives in the same repo as `paystore` core and depends on
it as a normal published dependency (`paystore = "^0.2.0"` — see
`pyproject.toml`), pulled from PyPI like any other requirement.

```bash
poetry install
poetry run pytest
```
