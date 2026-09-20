"""Remita provider implementation.

Remita's collections API (RRR flow) differs structurally from the other
providers: instead of a single Bearer API key, requests are authenticated
with a `merchant_id` + `service_type_id` + `api_key` + `api_secret` (the
latter two hashed together per-request, never sent directly). Pass these
via `Gateway(..., merchant_id=..., service_type_id=..., api_secret=...)`.

Implemented from Remita's published e-commerce/collections API docs;
Remita has historically shipped several API variants (RIMS, cREST,
e-commerce), so verify field names/status codes against the current docs
for your merchant account before relying on this in production.
"""

import hashlib
import hmac
from typing import Any, Dict, Optional

from paystore.core.base_provider import BaseProvider
from paystore.core.exceptions import ConfigurationError, PaymentError, ProviderError
from paystore.core.http_client import HTTPClient
from paystore.utils.helpers import generate_reference

_SUCCESS_STATUS_CODES = {"00", "01"}


class RemitaProvider(BaseProvider):
    """Remita payment provider (RRR-based collections flow)."""

    SUPPORTED_FEATURES = frozenset()  # no optional features

    SANDBOX_BASE_URL = "https://remitademo.net/remita/exapp/api/v1/send/api"
    LIVE_BASE_URL = "https://login.remita.net/remita/exapp/api/v1/send/api"
    SANDBOX_PAYMENT_URL = "https://remitademo.net/payment/v1/remita/ecomm/{rrr}/pay"
    LIVE_PAYMENT_URL = "https://login.remita.net/payment/v1/remita/ecomm/{rrr}/pay"

    def __init__(self, config):
        super().__init__(config)
        self._require_credentials()
        self.client = HTTPClient(config)

    def _require_credentials(self) -> None:
        missing = [
            name
            for name, value in (
                ("merchant_id", self.config.merchant_id),
                ("service_type_id", self.config.service_type_id),
                ("api_secret", self.config.api_secret),
            )
            if not value
        ]
        if missing:
            raise ConfigurationError(
                f"Remita requires {', '.join(missing)} in addition to api_key"
            )

    @property
    def base_url(self) -> str:
        return (
            self.LIVE_BASE_URL
            if self.config.environment == "production"
            else self.SANDBOX_BASE_URL
        )

    @property
    def payment_url_template(self) -> str:
        return (
            self.LIVE_PAYMENT_URL
            if self.config.environment == "production"
            else self.SANDBOX_PAYMENT_URL
        )

    def _init_hash(self, order_id: str, amount: Any) -> str:
        raw = (
            f"{self.config.api_key}{self.config.service_type_id}"
            f"{order_id}{amount}{self.config.api_secret}"
        )
        return hashlib.sha512(raw.encode()).hexdigest()

    def _status_hash(self, rrr: str) -> str:
        raw = f"{rrr}{self.config.api_key}{self.config.api_secret}"
        return hashlib.sha512(raw.encode()).hexdigest()

    def _get_headers(self, api_hash: str) -> Dict[str, str]:
        return {
            "Content-Type": "application/json",
            "Authorization": (
                f"remitaConsumerKey={self.config.api_key}, "
                f"remitaConsumerToken={api_hash}"
            ),
        }

    def initialize_payment(
        self, amount: int, email: str, currency: str = "NGN", **kwargs: Any
    ) -> Dict[str, Any]:
        """Generate a Remita Retrieval Reference (RRR) for the payment."""
        order_id = kwargs.pop("reference", None) or generate_reference()
        api_hash = self._init_hash(order_id, amount)

        url = (
            f"{self.base_url}/echannelsvc/{self.config.merchant_id}/"
            f"{self.config.service_type_id}/{self.config.api_key}/"
            "remita/ecomm/init.reg"
        )
        payload = {
            "serviceTypeId": self.config.service_type_id,
            "amount": amount,
            "orderId": order_id,
            "payerName": kwargs.pop("payer_name", None) or email,
            "payerEmail": email,
            "payerPhone": kwargs.pop("payer_phone", ""),
            "description": kwargs.pop("description", "Payment"),
            **kwargs,
        }

        try:
            response = self.client.post(
                url, data=payload, headers=self._get_headers(api_hash)
            )
            rrr = response.get("RRR")
            if not rrr:
                raise ProviderError(response.get("status", "Failed to generate RRR"))

            return {
                **response,
                "reference": order_id,
                "rrr": rrr,
                "authorization_url": self.payment_url_template.format(rrr=rrr),
                "access_code": rrr,
            }
        except PaymentError:
            raise
        except Exception as e:
            raise ProviderError(f"Failed to initialize payment: {e}") from e

    def verify_payment(self, reference: str) -> Dict[str, Any]:
        """
        Verify payment status by RRR.

        `reference` must be the RRR returned from `initialize_payment`
        (available as both `reference` and `rrr` in that response).
        """
        rrr = reference
        api_hash = self._status_hash(rrr)
        url = (
            f"{self.base_url}/echannelsvc/{self.config.merchant_id}/"
            f"{self.config.api_key}/{rrr}/{api_hash}/status.reg"
        )

        try:
            response = self.client.get(url, headers=self._get_headers(api_hash))
            status_code = str(response.get("status", ""))
            return {
                **response,
                "reference": rrr,
                "status": "success"
                if status_code in _SUCCESS_STATUS_CODES
                else "failed",
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
        """Not supported: Remita recurring payments use a separate mandate API."""
        raise NotImplementedError(
            f"{self.__class__.__name__} does not support charge_authorization; "
            "Remita recurring payments require its mandate/direct-debit API, "
            "which is not yet implemented"
        )

    def verify_webhook_signature(self, payload: bytes, signature: str) -> bool:
        """
        Verify a Remita webhook/IPN notification.

        Remita's IPN hash is `sha512(rrr + amount + api_key + order_id +
        api_secret)`. Since the exact fields sent differ by integration,
        callers should pass the provider's hash value as `signature` and
        the exact same raw fields Remita hashed (in Remita's documented
        order) as `payload`; this compares the two directly.
        """
        assert self.config.api_secret  # enforced by _require_credentials
        computed = hashlib.sha512(payload + self.config.api_secret.encode()).hexdigest()
        return hmac.compare_digest(computed, signature)
