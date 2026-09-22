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
    SUPPORTED_FEATURES = frozenset(
        {
            "charge_authorization",
            "customers",
            "tokens",
            "refunds",
            "subscriptions",
            "transfers",
        }
    )

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

    def refund_payment(
        self, reference: str, amount: Optional[int] = None, **kwargs: Any
    ) -> Dict[str, Any]:
        """Refund a Paystack transaction, in full or in part."""
        url = f"{self.BASE_URL}/refund"

        payload: Dict[str, Any] = {"transaction": reference, **kwargs}
        if amount is not None:
            payload["amount"] = amount

        try:
            response = self.client.post(url, data=payload, headers=self._get_headers())
            if response.get("status"):
                return response.get("data", {})
            raise ProviderError(response.get("message", "Refund failed"))
        except PaymentError:
            raise
        except Exception as e:
            raise ProviderError(f"Failed to refund payment: {e}") from e

    def create_plan(
        self,
        name: str,
        amount: int,
        interval: str,
        currency: str = "NGN",
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        Create a Paystack billing plan.

        interval: one of "hourly", "daily", "weekly", "monthly",
        "quarterly", "biannually", "annually".
        """
        url = f"{self.BASE_URL}/plan"
        payload = {
            "name": name,
            "amount": amount,
            "interval": interval,
            "currency": currency,
            **kwargs,
        }

        try:
            response = self.client.post(url, data=payload, headers=self._get_headers())
            if response.get("status"):
                return response.get("data", {})
            raise ProviderError(response.get("message", "Plan creation failed"))
        except PaymentError:
            raise
        except Exception as e:
            raise ProviderError(f"Failed to create plan: {e}") from e

    def create_subscription(
        self, customer: str, plan: str, **kwargs: Any
    ) -> Dict[str, Any]:
        """
        Subscribe a customer to a plan.

        customer: customer code or email. Pass authorization_code as a
        kwarg to pick a specific saved card; otherwise Paystack uses the
        customer's most recent successful authorization.
        """
        url = f"{self.BASE_URL}/subscription"
        payload = {"customer": customer, "plan": plan, **kwargs}

        try:
            response = self.client.post(url, data=payload, headers=self._get_headers())
            if response.get("status"):
                return response.get("data", {})
            raise ProviderError(response.get("message", "Subscription failed"))
        except PaymentError:
            raise
        except Exception as e:
            raise ProviderError(f"Failed to create subscription: {e}") from e

    def cancel_subscription(
        self, subscription_code: str, **kwargs: Any
    ) -> Dict[str, Any]:
        """
        Cancel a Paystack subscription.

        Paystack's disable endpoint requires an email_token in addition
        to the subscription code, so this fetches the subscription first
        to retrieve it.
        """
        try:
            subscription = self.client.get(
                f"{self.BASE_URL}/subscription/{subscription_code}",
                headers=self._get_headers(),
            )
            if not subscription.get("status"):
                raise ProviderError(
                    subscription.get("message", "Subscription not found")
                )
            email_token = subscription.get("data", {}).get("email_token")

            response = self.client.post(
                f"{self.BASE_URL}/subscription/disable",
                data={"code": subscription_code, "token": email_token, **kwargs},
                headers=self._get_headers(),
            )
            if response.get("status"):
                return {"success": True, "message": response.get("message")}
            raise ProviderError(response.get("message", "Cancellation failed"))
        except PaymentError:
            raise
        except Exception as e:
            raise ProviderError(f"Failed to cancel subscription: {e}") from e

    def create_transfer_recipient(
        self,
        name: str,
        account_number: str,
        bank_code: str,
        currency: str = "NGN",
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Register a NUBAN recipient to send payouts to."""
        url = f"{self.BASE_URL}/transferrecipient"
        payload = {
            "type": kwargs.pop("type", "nuban"),
            "name": name,
            "account_number": account_number,
            "bank_code": bank_code,
            "currency": currency,
            **kwargs,
        }

        try:
            response = self.client.post(url, data=payload, headers=self._get_headers())
            if response.get("status"):
                return response.get("data", {})
            raise ProviderError(response.get("message", "Recipient creation failed"))
        except PaymentError:
            raise
        except Exception as e:
            raise ProviderError(f"Failed to create transfer recipient: {e}") from e

    def initiate_transfer(
        self,
        recipient: Any,
        amount: int,
        reason: str = "",
        currency: str = "NGN",
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        Send a payout to a previously created recipient.

        `recipient` is the recipient_code returned by
        create_transfer_recipient.
        """
        url = f"{self.BASE_URL}/transfer"
        payload = {
            "source": kwargs.pop("source", "balance"),
            "amount": amount,
            "recipient": recipient,
            "reason": reason,
            "currency": currency,
            **kwargs,
        }

        try:
            response = self.client.post(url, data=payload, headers=self._get_headers())
            if response.get("status"):
                return response.get("data", {})
            raise ProviderError(response.get("message", "Transfer failed"))
        except PaymentError:
            raise
        except Exception as e:
            raise ProviderError(f"Failed to initiate transfer: {e}") from e

    def verify_webhook_signature(self, payload: bytes, signature: str) -> bool:
        """Verify Paystack webhook signature."""
        computed = hmac.new(
            self.config.api_key.encode(), payload, hashlib.sha512
        ).hexdigest()
        return hmac.compare_digest(computed, signature)
