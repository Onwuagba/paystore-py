"""Subscription Management Example."""

import os
from datetime import datetime, timedelta

from paystore.core.gateway import Gateway

# Simulated database
SUBSCRIPTIONS_DB = {}


class SubscriptionManager:
    """Manage subscriptions with tokenized payments."""

    def __init__(self):
        self.gateway = Gateway(
            provider="paystack",
            api_key=os.getenv("PAYSTACK_SECRET_KEY", "sk_test_demo"),
            environment="sandbox",
        )

    def create_subscription(self, email: str, plan: str = "monthly"):
        """Create new subscription."""
        plans = {"monthly": 9900, "yearly": 99900}
        amount = plans.get(plan, 9900)

        transaction = self.gateway.payments.initialize(
            amount=amount, email=email, metadata={"subscription": True, "plan": plan}
        )

        print(f"✓ Payment link: {transaction['authorization_url']}")
        return transaction

    def charge_due_subscriptions(self):
        """Charge all due subscriptions."""
        print("\nProcessing Due Subscriptions...")

        for email, sub in SUBSCRIPTIONS_DB.items():
            if sub["status"] != "active":
                continue

            if sub["next_charge_date"].date() > datetime.now().date():
                continue

            try:
                result = self.gateway.payments.charge_authorization(
                    authorization_code=sub["authorization_code"],
                    email=email,
                    amount=sub["amount"],
                )

                if result["status"] == "success":
                    print(f"✓ Charged {email}: ₦{sub['amount']/100}")
                    sub["next_charge_date"] = datetime.now() + timedelta(days=30)
            except Exception as e:
                print(f"✗ Error charging {email}: {e}")


def main():
    print("=" * 60)
    print("Subscription Management Example")
    print("=" * 60)

    manager = SubscriptionManager()

    # Create subscription
    print("\n1. Creating subscription...")
    manager.create_subscription("alice@example.com", "monthly")

    print("\n2. After customer pays, save authorization_code")
    print("3. Run charge_due_subscriptions() daily via cron")

    print("\n" + "=" * 60)


if __name__ == "__main__":
    main()
