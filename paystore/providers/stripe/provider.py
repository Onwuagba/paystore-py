"""Stripe provider implementation."""

import hashlib
import hmac
import time
from typing import Any, Dict, List, Optional

from paystore.core.base_provider import BaseProvider
from paystore.core.exceptions import ConfigurationError, PaymentError, ProviderError
from paystore.core.http_client import HTTPClient

_STATUS_MAP = {
    "paid": "success",
    "complete": "success",
    "succeeded": "success",
    "unpaid": "pending",
    "open": "pending",
    "requires_action": "pending",
    "requires_payment_method": "pending",
    "requires_confirmation": "pending",
    "processing": "pending",
    "canceled": "cancelled",
    "expired": "failed",
}


def _flatten_params(data: Dict[str, Any], parent_key: str = "") -> Dict[str, Any]:
    """
    Flatten a nested dict/list into Stripe's bracket-notation form fields.

    e.g. {"line_items": [{"quantity": 1}]} -> {"line_items[0][quantity]": 1}
    """
    flat: Dict[str, Any] = {}
    for key, value in data.items():
        full_key = f"{parent_key}[{key}]" if parent_key else str(key)
        if value is None:
            continue
        if isinstance(value, dict):
            flat.update(_flatten_params(value, full_key))
        elif isinstance(value, list):
            for index, item in enumerate(value):
                indexed_key = f"{full_key}[{index}]"
                if isinstance(item, dict):
                    flat.update(_flatten_params(item, indexed_key))
                else:
                    flat[indexed_key] = item
        elif isinstance(value, bool):
            flat[full_key] = "true" if value else "false"
        else:
            flat[full_key] = value
    return flat


class StripeProvider(BaseProvider):
    """
    Stripe payment provider.

    Uses Checkout Sessions for `initialize_payment` so the return shape
    (authorization_url/reference) matches the other providers. Note that
    Stripe does not support NGN; pass a currency Stripe supports (e.g. USD).

    `amount` is always the smallest currency unit (e.g. cents for USD),
    same as the other providers — except for zero-decimal currencies
    (JPY, KRW, etc.), where the smallest unit *is* the major unit; see
    paystore.utils.currency.is_zero_decimal_currency. Passing 500 for a
    JPY charge means ¥500, not ¥5.00.
    """

    BASE_URL = "https://api.stripe.com/v1"
    SUPPORTED_FEATURES = frozenset(
        {"charge_authorization", "customers", "tokens", "refunds", "subscriptions"}
    )

    def __init__(self, config):
        super().__init__(config)
        self.client = HTTPClient(config)

    def _get_headers(self) -> Dict[str, str]:
        return {"Authorization": f"Bearer {self.config.api_key}"}

    def _post(
        self,
        path: str,
        payload: Dict[str, Any],
        idempotency_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        url = f"{self.BASE_URL}/{path}"
        headers = self._get_headers()
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key
        response = self.client.post_form(
            url, data=_flatten_params(payload), headers=headers
        )
        if "error" in response:
            raise ProviderError(response["error"].get("message", "Stripe API error"))
        return response

    def _get(self, path: str) -> Dict[str, Any]:
        url = f"{self.BASE_URL}/{path}"
        response = self.client.get(url, headers=self._get_headers())
        if "error" in response:
            raise ProviderError(response["error"].get("message", "Stripe API error"))
        return response

    def _delete(self, path: str) -> Dict[str, Any]:
        url = f"{self.BASE_URL}/{path}"
        response = self.client.delete(url, headers=self._get_headers())
        if "error" in response:
            raise ProviderError(response["error"].get("message", "Stripe API error"))
        return response

    @staticmethod
    def _normalize_status(raw_status: Any) -> str:
        return _STATUS_MAP.get(str(raw_status).lower(), str(raw_status).lower())

    def initialize_payment(
        self, amount: int, email: str, currency: str = "NGN", **kwargs: Any
    ) -> Dict[str, Any]:
        """Create a Stripe Checkout Session for the payment."""
        success_url = kwargs.pop("success_url", "https://example.com/success")
        cancel_url = kwargs.pop("cancel_url", "https://example.com/cancel")
        reference = kwargs.pop("reference", None)
        description = kwargs.pop("description", "Payment")

        payload = {
            "mode": "payment",
            "success_url": success_url,
            "cancel_url": cancel_url,
            "customer_email": email,
            "client_reference_id": reference,
            "line_items": [
                {
                    "price_data": {
                        "currency": currency.lower(),
                        "product_data": {"name": description},
                        "unit_amount": amount,
                    },
                    "quantity": 1,
                }
            ],
            **kwargs,
        }

        try:
            data = self._post("checkout/sessions", payload)
            return {
                **data,
                "reference": data.get("client_reference_id") or data.get("id"),
                "authorization_url": data.get("url"),
                "access_code": data.get("id"),
            }
        except PaymentError:
            raise
        except Exception as e:
            raise ProviderError(f"Failed to initialize payment: {e}") from e

    def verify_payment(self, reference: str) -> Dict[str, Any]:
        """Verify a payment by its Checkout Session id."""
        try:
            data = self._get(f"checkout/sessions/{reference}")
            return {
                **data,
                "reference": data.get("id", reference),
                "status": self._normalize_status(data.get("payment_status")),
            }
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
        Charge a saved PaymentMethod off-session via a PaymentIntent.

        idempotency_key, if given, is sent as Stripe's native
        `Idempotency-Key` header — Stripe itself will return the original
        result for a retried request with the same key, rather than
        creating a second PaymentIntent.
        """
        payload = {
            "amount": amount,
            "currency": currency.lower(),
            "payment_method": authorization_code,
            "receipt_email": email,
            "confirm": True,
            "off_session": True,
            **kwargs,
        }

        try:
            data = self._post(
                "payment_intents", payload, idempotency_key=idempotency_key
            )
            return {
                **data,
                "reference": data.get("id"),
                "status": self._normalize_status(data.get("status")),
            }
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
        """Create a Stripe customer."""
        name = " ".join(part for part in (first_name, last_name) if part) or None
        payload = {"email": email, "name": name, "phone": phone, **kwargs}

        try:
            data = self._post("customers", payload)
            return {**data, "customer_code": data.get("id")}
        except PaymentError:
            raise
        except Exception as e:
            raise ProviderError(f"Failed to create customer: {e}") from e

    def get_customer(self, customer_code: str) -> Dict[str, Any]:
        """Get a Stripe customer by id."""
        try:
            data = self._get(f"customers/{customer_code}")
            return {**data, "customer_code": data.get("id")}
        except PaymentError:
            raise
        except Exception as e:
            raise ProviderError(f"Failed to get customer: {e}") from e

    def update_customer(self, customer_code: str, **kwargs: Any) -> Dict[str, Any]:
        """Update a Stripe customer."""
        try:
            data = self._post(f"customers/{customer_code}", kwargs)
            return {**data, "customer_code": data.get("id")}
        except PaymentError:
            raise
        except Exception as e:
            raise ProviderError(f"Failed to update customer: {e}") from e

    def list_customer_authorizations(self, customer_code: str) -> List[Dict[str, Any]]:
        """List a customer's saved card PaymentMethods."""
        try:
            data = self._get(f"payment_methods?customer={customer_code}&type=card")
            authorizations = []
            for pm in data.get("data", []):
                card = pm.get("card", {})
                authorizations.append(
                    {
                        **pm,
                        "authorization_code": pm.get("id"),
                        "brand": card.get("brand"),
                        "last4": card.get("last4"),
                        "exp_month": card.get("exp_month"),
                        "exp_year": card.get("exp_year"),
                        "reusable": True,
                    }
                )
            return authorizations
        except PaymentError:
            raise
        except Exception as e:
            raise ProviderError(f"Failed to list authorizations: {e}") from e

    def deactivate_authorization(self, authorization_code: str) -> Dict[str, Any]:
        """Detach a PaymentMethod from its customer."""
        try:
            data = self._post(f"payment_methods/{authorization_code}/detach", {})
            return {"success": True, **data}
        except PaymentError:
            raise
        except Exception as e:
            raise ProviderError(f"Failed to deactivate authorization: {e}") from e

    def refund_payment(
        self, reference: str, amount: Optional[int] = None, **kwargs: Any
    ) -> Dict[str, Any]:
        """
        Refund a Stripe payment, in full or in part.

        `reference` may be either a Checkout Session id ("cs_...", from
        initialize_payment — looked up to find its PaymentIntent) or a
        PaymentIntent id directly ("pi_...", as returned by
        charge_authorization).
        """
        try:
            payment_intent: Any = reference
            if reference.startswith("cs_"):
                session = self._get(f"checkout/sessions/{reference}")
                payment_intent = session.get("payment_intent")
                if not payment_intent:
                    raise ProviderError(
                        f"Checkout session {reference!r} has no completed payment"
                    )

            payload: Dict[str, Any] = {"payment_intent": payment_intent, **kwargs}
            if amount is not None:
                payload["amount"] = amount

            data = self._post("refunds", payload)
            return {**data, "reference": data.get("id")}
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
        Create a recurring Price (Stripe has no separate "plan" object
        since API version 2018-02-05; a Price with `recurring` set is
        the modern equivalent).

        interval: one of Stripe's interval values — "day", "week",
        "month", "year" (unlike Paystack's "daily"/"weekly"/etc — these
        are passed straight through, not translated between providers).
        """
        try:
            product = self._post("products", {"name": name})
            price = self._post(
                "prices",
                {
                    "unit_amount": amount,
                    "currency": currency.lower(),
                    "recurring": {"interval": interval},
                    "product": product.get("id"),
                    **kwargs,
                },
            )
            return {**price, "plan_code": price.get("id")}
        except PaymentError:
            raise
        except Exception as e:
            raise ProviderError(f"Failed to create plan: {e}") from e

    def create_subscription(
        self, customer: str, plan: str, **kwargs: Any
    ) -> Dict[str, Any]:
        """
        Subscribe a customer to a Price.

        customer: Stripe customer id. plan: a Price id (from create_plan).
        """
        try:
            data = self._post(
                "subscriptions",
                {"customer": customer, "items": [{"price": plan}], **kwargs},
            )
            return {**data, "subscription_code": data.get("id")}
        except PaymentError:
            raise
        except Exception as e:
            raise ProviderError(f"Failed to create subscription: {e}") from e

    def cancel_subscription(
        self, subscription_code: str, **kwargs: Any
    ) -> Dict[str, Any]:
        """Cancel a Stripe subscription immediately."""
        try:
            data = self._delete(f"subscriptions/{subscription_code}")
            return {"success": True, **data}
        except PaymentError:
            raise
        except Exception as e:
            raise ProviderError(f"Failed to cancel subscription: {e}") from e

    def verify_webhook_signature(self, payload: bytes, signature: str) -> bool:
        """
        Verify a Stripe webhook signature.

        `signature` is the raw `Stripe-Signature` header value
        (e.g. "t=1614556800,v1=<hex>"). Requires `webhook_secret` in Config
        (Stripe's whsec_... signing secret, distinct from the API key).
        """
        if not self.config.webhook_secret:
            raise ConfigurationError(
                "webhook_secret is required to verify Stripe webhooks"
            )

        parts = dict(item.split("=", 1) for item in signature.split(",") if "=" in item)
        timestamp = parts.get("t")
        expected_sig = parts.get("v1")
        if not timestamp or not expected_sig:
            return False

        signed_payload = f"{timestamp}.{payload.decode()}".encode()
        computed_sig = hmac.new(
            self.config.webhook_secret.encode(), signed_payload, hashlib.sha256
        ).hexdigest()

        if not hmac.compare_digest(computed_sig, expected_sig):
            return False

        tolerance_seconds = 300
        return abs(time.time() - int(timestamp)) <= tolerance_seconds
