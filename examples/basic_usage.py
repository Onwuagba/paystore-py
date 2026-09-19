#!/usr/bin/env python3
"""
Basic usage example showing different authentication methods.

Before running:
    # Method 1: Set environment variable
    export PAYSTACK_SECRET_KEY=sk_test_your_key

    # Method 2: Create .env file
    echo "PAYSTACK_SECRET_KEY=sk_test_your_key" > .env
"""

import os

from paystore.core.gateway import Gateway


def example_direct_credentials():
    """Example 1: Direct credentials (simplest)."""
    print("=" * 60)
    print("Example 1: Direct Credentials")
    print("=" * 60)

    gateway = Gateway(
        provider="paystack",
        api_key="sk_test_demo_key",  # Replace with your key
        environment="sandbox",
    )

    print("✓ Gateway initialized with direct credentials")
    return gateway


def example_environment_variables():
    """Example 2: Environment variables (recommended)."""
    print("\n" + "=" * 60)
    print("Example 2: Environment Variables")
    print("=" * 60)

    # The library automatically loads from PAYSTACK_SECRET_KEY
    if os.getenv("PAYSTACK_SECRET_KEY"):
        gateway = Gateway(provider="paystack")
        print("✓ Gateway initialized from PAYSTACK_SECRET_KEY")
        return gateway
    else:
        print("⚠ PAYSTACK_SECRET_KEY not set in environment")
        print("  Run: export PAYSTACK_SECRET_KEY=sk_test_your_key")
        return None


def example_dotenv():
    """Example 3: Using .env file (local development)."""
    print("\n" + "=" * 60)
    print("Example 3: Using .env File")
    print("=" * 60)

    try:
        from dotenv import load_dotenv

        load_dotenv()

        if os.getenv("PAYSTACK_SECRET_KEY"):
            gateway = Gateway(provider="paystack")
            print("✓ Gateway initialized from .env file")
            return gateway
        else:
            print("⚠ .env file not found or PAYSTACK_SECRET_KEY not set")
            print("  Create .env with: PAYSTACK_SECRET_KEY=sk_test_your_key")
    except ImportError:
        print("⚠ python-dotenv not installed")
        print("  Install with: pip install python-dotenv")

    return None


def example_initialize_payment(gateway):
    """Example payment initialization."""
    print("\n" + "=" * 60)
    print("Initializing Payment")
    print("=" * 60)

    try:
        transaction = gateway.payments.initialize(
            amount=50000,  # ₦500.00 (in kobo)
            email="customer@example.com",
            currency="NGN",
            metadata={"order_id": "12345", "customer_name": "John Doe"},
        )

        print("✓ Payment initialized successfully!")
        print(f"  Reference: {transaction.get('reference')}")
        print(f"  Payment URL: {transaction.get('authorization_url')}")
        print("\n  Customer should visit the URL to complete payment")

        return transaction

    except Exception as e:
        print(f"✗ Error: {e}")
        return None


def example_verify_payment(gateway, reference):
    """Example payment verification."""
    print("\n" + "=" * 60)
    print("Verifying Payment")
    print("=" * 60)

    try:
        result = gateway.payments.verify(reference)

        print(f"  Status: {result.get('status')}")
        print(f"  Amount: ₦{result.get('amount', 0) / 100:.2f}")
        print(f"  Reference: {result.get('reference')}")

        if result.get("status") == "success":
            print("\n✓ Payment successful!")
        else:
            print(f"\n⚠ Payment status: {result.get('status')}")

        return result

    except Exception as e:
        print(f"✗ Error: {e}")
        return None


def main():
    """Run all examples."""
    print("\n")
    print("╔" + "=" * 58 + "╗")
    print("║" + " " * 10 + "Payment Aggregator - Basic Examples" + " " * 13 + "║")
    print("╚" + "=" * 58 + "╝")

    # Try different authentication methods
    gateway = None

    # Try method 1: Direct credentials
    try:
        gateway = example_direct_credentials()
    except Exception as e:
        print(f"✗ Direct credentials failed: {e}")

    # Try method 2: Environment variables
    if not gateway:
        gateway = example_environment_variables()

    # Try method 3: .env file
    if not gateway:
        gateway = example_dotenv()

    # If we have a gateway, demonstrate payment operations
    if gateway:
        print("\n" + "=" * 60)
        print("DEMO: Payment Operations")
        print("=" * 60)
        print("\nNote: This is a demo. Actual payment requires valid credentials.")
        print("Update the api_key with your test key to try real payments.")

        # Uncomment these lines with valid credentials to test
        # transaction = example_initialize_payment(gateway)
        # if transaction:
        #     reference = transaction.get('reference')
        #     # After customer pays, verify:
        #     # result = example_verify_payment(gateway, reference)
    else:
        print("\n" + "=" * 60)
        print("No valid credentials found!")
        print("=" * 60)
        print("\nTo run this example, use one of these methods:")
        print("\n1. Set environment variable:")
        print("   export PAYSTACK_SECRET_KEY=sk_test_your_key")
        print("\n2. Create .env file:")
        print("   echo 'PAYSTACK_SECRET_KEY=sk_test_your_key' > .env")
        print("\n3. Edit this file and add your key to example_direct_credentials()")

    print("\n" + "=" * 60)
    print("Example completed!")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
