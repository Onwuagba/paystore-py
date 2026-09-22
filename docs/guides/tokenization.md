# Tokenization Guide

## What is Tokenization?

**Tokenization** allows you to securely save customer payment methods for future use without storing sensitive card data.

### Benefits

✅ **PCI-DSS Compliant** - Never store raw card data
✅ **Recurring Payments** - Charge customers automatically
✅ **Faster Checkout** - One-click payments
✅ **Subscriptions** - Easy subscription billing

## Basic Flow

```python
from paystore import Gateway

gateway = Gateway(provider="paystack", api_key="sk_test_...")

# Step 1: Initialize payment (customer enters card)
transaction = gateway.payments.initialize(
    amount=10000,
    email="customer@example.com"
)

# Step 2: Customer completes payment
# Webhook receives authorization_code

# Step 3: Charge saved card later
result = gateway.payments.charge_authorization(
    authorization_code="AUTH_abc123",
    email="customer@example.com",
    amount=5000
)
```

## Customer Management

```python
# Create customer
customer = gateway.customers.create(
    email="customer@example.com",
    first_name="John",
    last_name="Doe"
)

# List customer's saved cards
tokens = gateway.tokens.list_for_customer(customer['customer_code'])

# Display cards to user
from paystore.security.tokenization import TokenManager

for token in tokens:
    display = TokenManager.format_card_display(token)
    print(display)  # "Visa •••• 4242 (Expires 12/2025)"

# Remove a card
gateway.tokens.deactivate("AUTH_abc123")
```

## Subscription Example

For a manual cron-driven subscription loop (works with every provider
that supports charge_authorization):

```python
# Monthly subscription
result = gateway.payments.charge_authorization(
    authorization_code="AUTH_abc123",
    email="customer@example.com",
    amount=9900,  # ₦99/month
    idempotency_key=f"sub-{subscription_id}-{billing_period}",  # avoid double-charging on retry
)

if result['status'] == 'success':
    print("Subscription charged successfully!")
```

Paystack and Stripe also expose their native recurring-billing objects
(handles retries/dunning for you) via `gateway.subscriptions` — see the
"Refunds and recurring billing" section of the main README.

## Security Best Practices

- ✅ Never store raw card details
- ✅ Only store authorization codes
- ✅ Verify webhook signatures
- ✅ Let users manage their saved cards
- ✅ Check token expiry before charging

See full documentation for more examples and best practices.
