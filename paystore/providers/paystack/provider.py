"""Paystack provider implementation."""

import hashlib
import hmac
from typing import Any, Dict, List, Optional

from paystore.core.base_provider import BaseProvider
from paystore.core.exceptions import PaymentError, ProviderError
from paystore.core.http_client import HTTPClient


class PaystackProvider(BaseProvider):
    """Paystack payment provider."""

    BASE_URL = "https://api.paystack.co"
    SUPPORTED_FEATURES = frozenset({"charge_authorization", "customers", "tokens"})

    def __init__(self, config):
        super().__init__(config)
        self.client = HTTPClient(config)

    def _get_headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
        }

    def initialize_payment(
        self, amount: int, email: str, currency: str = "NGN", **kwargs: Any
    ) -> Dict[str, Any]:
        """Initialize payment with Paystack."""
        url = f"{self.BASE_URL}/transaction/initialize"
        payload = {"amount": amount, "email": email, "currency": currency, **kwargs}

        try:
            response = self.client.post(url, data=payload, headers=self._get_headers())
            if response.get("status"):
                return response.get("data", {})
            raise ProviderError(response.get("message", "Unknown error"))
        except PaymentError:
            raise
        except Exception as e:
            raise ProviderError(f"Failed to initialize payment: {e}") from e

    def verify_payment(self, reference: str) -> Dict[str, Any]:
        """Verify payment with Paystack."""
        url = f"{self.BASE_URL}/transaction/verify/{reference}"

        try:
            response = self.client.get(url, headers=self._get_headers())
            if response.get("status"):
                return response.get("data", {})
            raise ProviderError(response.get("message", "Verification failed"))
        except PaymentError:
            raise
        except Exception as e:
            raise ProviderError(f"Failed to verify payment: {e}") from e

    def charge_authorization(
        self,
        authorization_code: str,
        email: str,
        amount: int,
        currency: str = "NGN",
        idempotency_key: Optional[str] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        Charge a tokenized card using authorization code.

        Paystack's API has no documented native idempotency-key support,
        so idempotency_key is accepted for interface consistency but not
        sent to Paystack — Gateway.payments.charge_authorization still
        dedupes retries by this key at the client level.
        """
        url = f"{self.BASE_URL}/transaction/charge_authorization"

        payload = {
            "authorization_code": authorization_code,
            "email": email,
            "amount": amount,
            "currency": currency,
            **kwargs,
        }

        try:
            response = self.client.post(url, data=payload, headers=self._get_headers())
            if response.get("status"):
                return response.get("data", {})
            raise ProviderError(response.get("message", "Charge failed"))
        except PaymentError:
            raise
        except Exception as e:
            raise ProviderError(f"Failed to charge authorization: {e}") from e

    def create_customer(
        self,
        email: str,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        phone: Optional[str] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Create a customer profile in Paystack."""
        url = f"{self.BASE_URL}/customer"

        payload = {"email": email}
        if first_name:
            payload["first_name"] = first_name
        if last_name:
            payload["last_name"] = last_name
        if phone:
            payload["phone"] = phone
        payload.update(kwargs)

        try:
            response = self.client.post(url, data=payload, headers=self._get_headers())
            if response.get("status"):
                return response.get("data", {})
            raise ProviderError(response.get("message", "Customer creation failed"))
        except PaymentError:
            raise
        except Exception as e:
            raise ProviderError(f"Failed to create customer: {e}") from e

    def get_customer(self, customer_code: str) -> Dict[str, Any]:
        """Get customer details from Paystack."""
        url = f"{self.BASE_URL}/customer/{customer_code}"

        try:
            response = self.client.get(url, headers=self._get_headers())
            if response.get("status"):
                return response.get("data", {})
            raise ProviderError(response.get("message", "Customer not found"))
        except PaymentError:
            raise
        except Exception as e:
            raise ProviderError(f"Failed to get customer: {e}") from e

    def update_customer(self, customer_code: str, **kwargs: Any) -> Dict[str, Any]:
        """Update customer details in Paystack."""
        url = f"{self.BASE_URL}/customer/{customer_code}"

        try:
            response = self.client.post(url, data=kwargs, headers=self._get_headers())
            if response.get("status"):
                return response.get("data", {})
            raise ProviderError(response.get("message", "Update failed"))
        except PaymentError:
            raise
        except Exception as e:
            raise ProviderError(f"Failed to update customer: {e}") from e

    def list_customer_authorizations(self, customer_code: str) -> List[Dict[str, Any]]:
        """List all payment tokens for a customer."""
        url = f"{self.BASE_URL}/customer/{customer_code}"

        try:
            response = self.client.get(url, headers=self._get_headers())
            if response.get("status"):
                data = response.get("data", {})
                return data.get("authorizations", [])
            raise ProviderError(
                response.get("message", "Failed to list authorizations")
            )
        except PaymentError:
            raise
        except Exception as e:
            raise ProviderError(f"Failed to list authorizations: {e}") from e

    def deactivate_authorization(self, authorization_code: str) -> Dict[str, Any]:
        """Deactivate a payment token."""
        url = f"{self.BASE_URL}/customer/deactivate_authorization"

        payload = {"authorization_code": authorization_code}

        try:
            response = self.client.post(url, data=payload, headers=self._get_headers())
            if response.get("status"):
                return {"success": True, "message": response.get("message")}
            raise ProviderError(response.get("message", "Deactivation failed"))
        except PaymentError:
            raise
        except Exception as e:
            raise ProviderError(f"Failed to deactivate authorization: {e}") from e

    def verify_webhook_signature(self, payload: bytes, signature: str) -> bool:
        """Verify Paystack webhook signature."""
        computed = hmac.new(
            self.config.api_key.encode(), payload, hashlib.sha512
        ).hexdigest()
        return hmac.compare_digest(computed, signature)
