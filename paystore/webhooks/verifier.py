"""Webhook verification."""

from paystore.core.exceptions import PaymentError


class WebhookVerifier:
    """Verify webhook signatures."""

    def __init__(self, provider):
        self.provider = provider

    def verify(self, payload: bytes, signature: str) -> bool:
        """Verify webhook signature."""
        is_valid = self.provider.verify_webhook_signature(payload, signature)
        if not is_valid:
            raise PaymentError("Invalid webhook signature")
        return True
