#!/usr/bin/env python3
"""Multi-Provider Example - switch gateways by changing one string."""

import os

from paystore import Gateway


def initialize_with(provider: str, email: str, amount: int, currency: str):
    """Initialize a payment with any supported provider."""
    gateway = Gateway(provider=provider, environment="sandbox")

    transaction = gateway.payments.initialize(
        amount=amount, email=email, currency=currency
    )
    print(f"[{provider}] Payment URL: {transaction['authorization_url']}")
    print(f"[{provider}] Reference:  {transaction['reference']}")
    return transaction


def main():
    print("=" * 60)
    print("Multi-Provider Example")
    print("=" * 60)

    print("\nNote: requires PAYSTACK_SECRET_KEY, FLUTTERWAVE_SECRET_KEY,")
    print("and/or STRIPE_SECRET_KEY to be set. Stripe does not support NGN.\n")

    if os.getenv("PAYSTACK_SECRET_KEY"):
        initialize_with("paystack", "customer@example.com", 10000, "NGN")

    if os.getenv("FLUTTERWAVE_SECRET_KEY"):
        initialize_with("flutterwave", "customer@example.com", 10000, "NGN")

    if os.getenv("STRIPE_SECRET_KEY"):
        initialize_with("stripe", "customer@example.com", 1000, "USD")

    print("\n" + "=" * 60)
    print("Example complete! Same code, three gateways.")
    print("=" * 60)


if __name__ == "__main__":
    main()
