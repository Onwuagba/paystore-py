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

    Flutterwave's "Payment Plans" attach recurring billing to a regular
    initialize_payment call (via a payment_plan kwarg) rather than
    exposing a separate create-subscription/cancel-subscription API per
    customer the way Paystack/Stripe do, so create_plan/
    create_subscription/cancel_subscription aren't implemented here
    either — use `initialize_payment(..., payment_plan=plan_id)` instead.

    Transfers don't need a separate "recipient" object the way
    Paystack's do — create_transfer_recipient isn't implemented;
    initiate_transfer takes bank account details directly (see its
    docstring).
    """

    BASE_URL = "https://api.flutterwave.com/v3"
    SUPPORTED_FEATURES = frozenset({"charge_authorization", "refunds", "transfers"})

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

    def refund_payment(
        self, reference: str, amount: Optional[int] = None, **kwargs: Any
    ) -> Dict[str, Any]:
        """
        Refund a Flutterwave transaction, in full or in part.

        Flutterwave's refund endpoint is keyed by its own numeric
        transaction id, not tx_ref, so this looks the transaction up by
        reference first (one extra request) to resolve it.
        """
        try:
            transaction = self.verify_payment(reference)
            transaction_id = transaction.get("id")
            if not transaction_id:
                raise ProviderError(
                    f"Could not resolve transaction id for {reference!r}"
                )

            url = f"{self.BASE_URL}/transactions/{transaction_id}/refund"
            payload: Dict[str, Any] = {**kwargs}
            if amount is not None:
                payload["amount"] = amount

            response = self.client.post(url, data=payload, headers=self._get_headers())
            if response.get("status") == "success":
                return response.get("data", {})
            raise ProviderError(response.get("message", "Refund failed"))
        except PaymentError:
            raise
        except Exception as e:
            raise ProviderError(f"Failed to refund payment: {e}") from e

    def initiate_transfer(
        self,
        recipient: Any,
        amount: int,
        reason: str = "",
        currency: str = "NGN",
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        Send a payout.

        `recipient` must be a dict with `account_bank` (Flutterwave's
        bank code) and `account_number`, and optionally
        `beneficiary_name` — Flutterwave has no separate "recipient"
        object to create ahead of time, unlike Paystack.
        """
        url = f"{self.BASE_URL}/transfers"
        tx_ref = kwargs.pop("reference", None) or generate_reference()

        payload = {
            "account_bank": recipient.get("account_bank"),
            "account_number": recipient.get("account_number"),
            "beneficiary_name": recipient.get("beneficiary_name"),
            "amount": amount,
            "narration": reason,
            "currency": currency,
            "reference": tx_ref,
            **kwargs,
        }

        try:
            response = self.client.post(url, data=payload, headers=self._get_headers())
            if response.get("status") == "success":
                data = response.get("data", {})
                return {**data, "reference": data.get("reference", tx_ref)}
            raise ProviderError(response.get("message", "Transfer failed"))
        except PaymentError:
            raise
        except Exception as e:
            raise ProviderError(f"Failed to initiate transfer: {e}") from e

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
