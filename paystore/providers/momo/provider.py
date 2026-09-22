"""MTN Mobile Money (MoMo) Collections provider implementation.

MoMo's integration model differs from the other providers more than
any other provider here, documented on each affected method. Config
field mapping (MoMo's credential set doesn't match paystore's
api_key/api_secret/webhook_secret 1:1, so these are repurposed):

- `api_key`: MoMo's "API User" (a UUID you provision once via MTN's
  developer portal/sandbox provisioning — not something this provider
  does for you).
- `api_secret`: MoMo's "API Key" for that API User (also provisioned
  once, required).
- `webhook_secret`: MoMo's Ocp-Apim-Subscription-Key (the Collections
  product's subscription key — required on *every* request, not just
  webhooks; repurposed here since it's the closest fit among existing
  Config fields).
- `merchant_id`: MoMo's X-Target-Environment header value — "sandbox"
  for testing (the default if omitted), or your country deployment
  (e.g. "mtnuganda", "mtnghana") in production.

Payments are collected via a USSD/app prompt sent directly to the
payer's phone, not a hosted checkout URL — pass the payer's MSISDN as
`phone` (required) to initialize_payment; `email` is accepted (it's
part of every provider's interface) but unused by MoMo. There's no
saved-card equivalent, so charge_authorization is not implemented.

Amounts are decimal strings in MoMo's API ("10.00"), not the minor-
unit ints this library's interface uses elsewhere — converted
internally (zero-decimal currencies excepted, same as PayPal/Stripe).

Implemented from MTN MoMo's published Collections API docs, not
verified against a live account (same caveat as Remita/PayPal) — the
production base URL in particular varies by MTN partner/country
deployment and may need overriding for your account.
"""

import base64
import time
from typing import Any, Dict, Optional

from paystore.core.base_provider import BaseProvider
from paystore.core.exceptions import ConfigurationError, PaymentError, ProviderError
from paystore.core.http_client import HTTPClient
from paystore.utils.currency import to_decimal_string
from paystore.utils.helpers import generate_reference

_STATUS_MAP = {
    "SUCCESSFUL": "success",
    "PENDING": "pending",
    "FAILED": "failed",
}


class MomoProvider(BaseProvider):
    """MTN Mobile Money Collections provider."""

    SANDBOX_BASE_URL = "https://sandbox.momodeveloper.mtn.com"
    LIVE_BASE_URL = "https://proxy.momoapi.mtn.com"
    SUPPORTED_FEATURES = frozenset()  # no optional features

    def __init__(self, config):
        super().__init__(config)
        self._require_credentials()
        self.client = HTTPClient(config)
        self._access_token: Optional[str] = None
        self._token_expires_at: float = 0.0

    def _require_credentials(self) -> None:
        missing = [
            name
            for name, value in (
                ("api_secret", self.config.api_secret),
                ("webhook_secret", self.config.webhook_secret),
            )
            if not value
        ]
        if missing:
            raise ConfigurationError(
                f"MoMo requires {', '.join(missing)} in addition to api_key "
                "(see paystore.providers.momo.provider's module docstring "
                "for what each field maps to)"
            )

    @property
    def base_url(self) -> str:
        return (
            self.LIVE_BASE_URL
            if self.config.environment == "production"
            else self.SANDBOX_BASE_URL
        )

    @property
    def target_environment(self) -> str:
        return self.config.merchant_id or "sandbox"

    def _get_access_token(self) -> str:
        if self._access_token and time.time() < self._token_expires_at:
            return self._access_token

        assert self.config.api_secret  # enforced by _require_credentials
        credentials = base64.b64encode(
            f"{self.config.api_key}:{self.config.api_secret}".encode()
        ).decode()

        response = self.client.post(
            f"{self.base_url}/collection/token/",
            data={},
            headers={
                "Authorization": f"Basic {credentials}",
                "Ocp-Apim-Subscription-Key": self.config.webhook_secret or "",
            },
        )
        token = response.get("access_token")
        if not token:
            raise ProviderError("MoMo did not return an access token")

        self._access_token = token
        self._token_expires_at = time.time() + response.get("expires_in", 3600) - 60
        return token

    def _get_headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self._get_access_token()}",
            "Ocp-Apim-Subscription-Key": self.config.webhook_secret or "",
            "Content-Type": "application/json",
        }

    def charge_authorization(
        self,
        authorization_code: str,
        email: str,
        amount: int,
        currency: str = "NGN",
        idempotency_key: Optional[str] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Not supported: MoMo has no saved-payment-method concept."""
        raise NotImplementedError(
            f"{self.__class__.__name__} does not support charge_authorization; "
            "MTN MoMo has no saved-payment-method equivalent"
        )

    def initialize_payment(
        self, amount: int, email: str, currency: str = "NGN", **kwargs: Any
    ) -> Dict[str, Any]:
        """
        Send a Request to Pay — a USSD/app prompt to the payer's phone.

        Requires `phone` (the payer's MSISDN) via kwargs; `email` is
        unused. Returns immediately with status "pending" — MoMo's API
        responds 202 with no payment result yet; poll verify_payment
        with the returned reference to find out what happened.
        """
        phone = kwargs.pop("phone", None)
        if not phone:
            raise ProviderError(
                "MoMo requires a `phone` kwarg (the payer's MSISDN) — "
                "email alone can't receive a payment prompt"
            )
        reference = kwargs.pop("reference", None) or generate_reference()

        payload = {
            "amount": to_decimal_string(amount, currency),
            "currency": currency,
            "externalId": reference,
            "payer": {"partyIdType": "MSISDN", "partyId": phone},
            "payerMessage": kwargs.pop("payer_message", "Payment"),
            "payeeNote": kwargs.pop("payee_note", "Payment"),
            **kwargs,
        }
        headers = self._get_headers()
        headers["X-Reference-Id"] = reference
        headers["X-Target-Environment"] = self.target_environment

        try:
            self.client.post(
                f"{self.base_url}/collection/v1_0/requesttopay",
                data=payload,
                headers=headers,
            )
            return {
                "reference": reference,
                "status": "pending",
                "authorization_url": None,
            }
        except PaymentError:
            raise
        except Exception as e:
            raise ProviderError(f"Failed to initialize payment: {e}") from e

    def verify_payment(self, reference: str) -> Dict[str, Any]:
        """Check a Request to Pay's status by its reference."""
        headers = self._get_headers()
        headers["X-Target-Environment"] = self.target_environment

        try:
            response = self.client.get(
                f"{self.base_url}/collection/v1_0/requesttopay/{reference}",
                headers=headers,
            )
            status = _STATUS_MAP.get(str(response.get("status", "")).upper(), "failed")
            return {**response, "reference": reference, "status": status}
        except PaymentError:
            raise
        except Exception as e:
            raise ProviderError(f"Failed to verify payment: {e}") from e

    def verify_webhook_signature(self, payload: bytes, signature: str) -> bool:
        """
        Not implemented: MTN's callback notifications (the X-Callback-Url
        you register) have no publicly standardized signature scheme
        across deployments — unlike every other provider here, there's
        no HMAC/signing-secret check to implement honestly. Verify
        payment status by polling verify_payment(reference) instead of
        trusting an unauthenticated callback body, or rely on network-
        level controls (IP allowlisting) for your specific deployment.
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} does not support webhook signature "
            "verification — poll verify_payment(reference) instead"
        )
