"""Flutterwave provider implementation."""

import hmac
from typing import Any, Dict, Optional

from paystore.core.base_provider import BaseProvider
from paystore.core.exceptions import ConfigurationError, PaymentError, ProviderError
from paystore.core.http_client import HTTPClient
from paystore.utils.helpers import generate_reference

_STATUS_MAP = {
    "successful": "success",
    "success": "success",
    "failed": "failed",
    "pending": "pending",
    "cancelled": "cancelled",
}


class FlutterwaveProvider(BaseProvider):
    """
    Flutterwave payment provider.

    Note: Flutterwave has no first-class "saved customer" API comparable to
    Paystack's, so create_customer/get_customer/update_customer/
    list_customer_authorizations/deactivate_authorization are not
    implemented and raise NotImplementedError (see BaseProvider defaults).
    Recurring charges are still supported via charge_authorization, which
    uses the card token returned in a verified transaction's payload.
    """

    BASE_URL = "https://api.flutterwave.com/v3"

    def __init__(self, config):
        super().__init__(config)
        self.client = HTTPClient(config)

    def _get_headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
        }

    @staticmethod
    def _normalize_status(raw_status: Any) -> str:
        return _STATUS_MAP.get(str(raw_status).lower(), str(raw_status).lower())

    def initialize_payment(
        self, amount: int, email: str, currency: str = "NGN", **kwargs: Any
    ) -> Dict[str, Any]:
        """Initialize payment with Flutterwave."""
        url = f"{self.BASE_URL}/payments"
        tx_ref = kwargs.pop("reference", None) or generate_reference()
        redirect_url = kwargs.pop("redirect_url", None) or kwargs.pop(
            "callback_url", "https://example.com/callback"
        )

        payload = {
            "tx_ref": tx_ref,
            "amount": amount,
            "currency": currency,
            "redirect_url": redirect_url,
            "customer": {"email": email},
            **kwargs,
        }

        try:
            response = self.client.post(url, data=payload, headers=self._get_headers())
            if response.get("status") == "success":
                data = response.get("data", {})
                return {
                    **data,
                    "reference": tx_ref,
                    "authorization_url": data.get("link"),
                    "access_code": None,
                }
            raise ProviderError(response.get("message", "Unknown error"))
        except PaymentError:
            raise
        except Exception as e:
            raise ProviderError(f"Failed to initialize payment: {e}") from e

    def verify_payment(self, reference: str) -> Dict[str, Any]:
        """Verify payment with Flutterwave using the transaction reference."""
        url = f"{self.BASE_URL}/transactions/verify_by_reference"

        try:
            response = self.client.get(
                f"{url}?tx_ref={reference}", headers=self._get_headers()
            )
            if response.get("status") == "success":
                data = response.get("data", {})
                return {
                    **data,
                    "reference": data.get("tx_ref", reference),
                    "status": self._normalize_status(data.get("status")),
                }
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
        Charge a saved card token via Flutterwave's tokenized-charges endpoint.

        Flutterwave has no documented native idempotency-key support, so
        idempotency_key is accepted for interface consistency but not
        sent — Gateway.payments.charge_authorization still dedupes
        retries by this key at the client level.
        """
        url = f"{self.BASE_URL}/tokenized-charges"
        tx_ref = kwargs.pop("reference", None) or generate_reference()

        payload = {
            "token": authorization_code,
            "email": email,
            "amount": amount,
            "currency": currency,
            "tx_ref": tx_ref,
            **kwargs,
        }

        try:
            response = self.client.post(url, data=payload, headers=self._get_headers())
            if response.get("status") == "success":
                data = response.get("data", {})
                return {
                    **data,
                    "reference": data.get("tx_ref", tx_ref),
                    "status": self._normalize_status(data.get("status")),
                }
            raise ProviderError(response.get("message", "Charge failed"))
        except PaymentError:
            raise
        except Exception as e:
            raise ProviderError(f"Failed to charge authorization: {e}") from e

    def verify_webhook_signature(self, payload: bytes, signature: str) -> bool:
        """
        Verify Flutterwave webhook signature.

        Flutterwave does not sign the payload; it sends the `verif-hash`
        header set to the secret hash configured in the dashboard, which
        must match exactly. Requires `webhook_secret` in Config (or the
        FLUTTERWAVE_WEBHOOK_SECRET/PAYMENT_WEBHOOK_SECRET env vars).
        """
        if not self.config.webhook_secret:
            raise ConfigurationError(
                "webhook_secret is required to verify Flutterwave webhooks"
            )
        return hmac.compare_digest(self.config.webhook_secret, signature)
