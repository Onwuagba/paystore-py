#!/usr/bin/env python3
"""Tokenization Example - Save and reuse payment methods."""

import os

from paystore import Gateway
from paystore.security.tokenization import TokenManager


def main():
    print("=" * 60)
    print("Tokenization Example")
    print("=" * 60)

    gateway = Gateway(
        provider="paystack",
        api_key=os.getenv("PAYSTACK_SECRET_KEY", "sk_test_demo"),
        environment="sandbox",
    )

    # Create customer
    print("\n1. Creating customer profile...")
    try:
        customer = gateway.customers.create(
            email="john.doe@example.com", first_name="John", last_name="Doe"
        )
        print(f"✓ Customer created: {customer['customer_code']}")
        customer_code = customer["customer_code"]
    except Exception as e:
        print(f"✗ Error: {e}")
        return

    # Initialize payment
    print("\n2. Initializing payment...")
    transaction = gateway.payments.initialize(
        amount=10000, email="john.doe@example.com", metadata={"save_card": True}
    )
    print(f"✓ Payment URL: {transaction['authorization_url']}")
    print("  → Customer completes payment, webhook provides authorization_code")

    # List saved cards
    print("\n3. Listing saved payment methods...")
    try:
        tokens = gateway.tokens.list_for_customer(customer_code)
        for token in tokens:
            display = TokenManager.format_card_display(token)
            print(f"  • {display}")
    except Exception as e:
        print(f"  Note: {e}")

    # Charge authorization (example)
    print("\n4. Charging saved card (requires real auth code):")
    print(
        """
    result = gateway.payments.charge_authorization(
        authorization_code="AUTH_abc123",
        email="john.doe@example.com",
        amount=5000
    )
    """
    )

    print("\n" + "=" * 60)
    print("Example Complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()
