"""Paystack provider implementation."""

import hmac
import hashlib
from typing import Dict, Any
from paystore.core.base_provider import BaseProvider
from paystore.core.http_client import HTTPClient
from paystore.core.exceptions import ProviderError


class PaystackProvider(BaseProvider):
    """Paystack payment provider."""
    
    BASE_URL = "https://api.paystack.co"
    
    def __init__(self, config): 
        super().__init__(config)
        self.client = HTTPClient(config)
    
    def _get_headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json"
        }
    
    def initialize_payment(self, amount: int, email: str, currency: str = "NGN", **kwargs: Any) -> Dict[str, Any]:
        """Initialize payment with Paystack."""
        url = f"{self.BASE_URL}/transaction/initialize"
        payload = {"amount": amount, "email": email, "currency": currency, **kwargs}
        
        try:
            response = self.client.post(url, data=payload, headers=self._get_headers())
            if response.get("status"):
                return response.get("data", {})
            raise ProviderError(response.get("message", "Unknown error"))
        except Exception as e:
            raise ProviderError(f"Failed to initialize payment: {e}")
    
    def verify_payment(self, reference: str) -> Dict[str, Any]:
        """Verify payment with Paystack."""
        url = f"{self.BASE_URL}/transaction/verify/{reference}"
        
        try:
            response = self.client.get(url, headers=self._get_headers())
            if response.get("status"):
                return response.get("data", {})
            raise ProviderError(response.get("message", "Verification failed"))
        except Exception as e:
            raise ProviderError(f"Failed to verify payment: {e}")
    
    def verify_webhook_signature(self, payload: bytes, signature: str) -> bool:
        """Verify Paystack webhook signature."""
        computed = hmac.new(self.config.api_key.encode(), payload, hashlib.sha512).hexdigest()
        return hmac.compare_digest(computed, signature)
