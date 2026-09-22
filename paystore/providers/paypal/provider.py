"""PayPal provider implementation.

PayPal's integration model differs from the other providers in several
ways this provider works around, documented on each affected method:

- Auth is OAuth2 client credentials, not a static Bearer key: pass the
  PayPal REST app's Client ID as `api_key` and its Client Secret as
  `api_secret` (both required). An access token is fetched and cached
  automatically, refreshed shortly before it expires.
- Amounts are decimal major-unit strings in PayPal's API ("10.00"), not
  the smallest-unit integers every other provider (and this library's
  public interface) uses — converted internally, so `amount` is still
  always minor units here too (1000 for $10.00), except for
  zero-decimal currencies (see paystore.utils.currency).
- Order creation (initialize_payment) doesn't complete a payment by
  itself; the customer must approve it, then it must be *captured*.
  verify_payment does the capture for you if the order is APPROVED.
- Webhook signature verification needs several header values, not one
  signature string — see verify_webhook_signature's docstring.

Implemented from PayPal's published Orders v2 / Webhooks docs, not
verified against a live account — double-check field names/status
codes for your app before relying on this in production (same caveat
as Remita).
"""

import base64
import json
import time
from typing import Any, Dict, Optional

from paystore.core.base_provider import BaseProvider
from paystore.core.exceptions import ConfigurationError, PaymentError, ProviderError
from paystore.core.http_client import HTTPClient
from paystore.utils.currency import is_zero_decimal_currency
from paystore.utils.helpers import generate_reference


def _format_amount(amount: int, currency: str) -> str:
    """Convert a minor-unit int amount to PayPal's decimal string format."""
    if is_zero_decimal_currency(currency):
        return str(amount)
    return f"{amount / 100:.2f}"


class PaypalProvider(BaseProvider):
    """
    PayPal payment provider (Orders v2 API).

    Does not support NGN — pass a currency PayPal supports (e.g. USD).
    Only initialize/verify/refund/webhooks are implemented: PayPal's
    saved-payment-method equivalent (Vault) and payout equivalent
    (Payouts) are different enough products that force-fitting them
    into charge_authorization/transfers here would be misleading.
    """

    SANDBOX_BASE_URL = "https://api-m.sandbox.paypal.com"
    LIVE_BASE_URL = "https://api-m.paypal.com"
    SUPPORTED_FEATURES = frozenset({"refunds"})

    def __init__(self, config):
        super().__init__(config)
        self._require_credentials()
        self.client = HTTPClient(config)
        self._access_token: Optional[str] = None
        self._token_expires_at: float = 0.0

    def _require_credentials(self) -> None:
        if not self.config.api_secret:
            raise ConfigurationError(
                "PayPal requires api_secret (the app's Client Secret) in "
                "addition to api_key (the app's Client ID)"
            )

    @property
    def base_url(self) -> str:
        return (
            self.LIVE_BASE_URL
            if self.config.environment == "production"
            else self.SANDBOX_BASE_URL
        )

    def _get_access_token(self) -> str:
        if self._access_token and time.time() < self._token_expires_at:
            return self._access_token

        assert self.config.api_secret  # enforced by _require_credentials
        credentials = base64.b64encode(
            f"{self.config.api_key}:{self.config.api_secret}".encode()
        ).decode()

        response = self.client.post_form(
            f"{self.base_url}/v1/oauth2/token",
            data={"grant_type": "client_credentials"},
            headers={"Authorization": f"Basic {credentials}"},
        )
        token = response.get("access_token")
        if not token:
            raise ProviderError("PayPal did not return an access token")

        self._access_token = token
        # Refresh a little early so a near-expiry token isn't used mid-request.
        self._token_expires_at = time.time() + response.get("expires_in", 3600) - 60
        return token

    def _get_headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self._get_access_token()}",
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
        """Not supported: PayPal's saved-payment-method product (Vault) is separate."""
        raise NotImplementedError(
            f"{self.__class__.__name__} does not support charge_authorization; "
            "PayPal's saved-payment-method product (Vault) is not yet implemented"
        )

    def initialize_payment(
        self, amount: int, email: str, currency: str = "NGN", **kwargs: Any
    ) -> Dict[str, Any]:
        """Create a PayPal Order the customer must approve."""
        url = f"{self.base_url}/v2/checkout/orders"
        reference = kwargs.pop("reference", None) or generate_reference()
        return_url = kwargs.pop("return_url", "https://example.com/success")
        cancel_url = kwargs.pop("cancel_url", "https://example.com/cancel")

        payload = {
            "intent": "CAPTURE",
            "purchase_units": [
                {
                    "reference_id": reference,
                    "amount": {
                        "currency_code": currency,
                        "value": _format_amount(amount, currency),
                    },
                }
            ],
            "application_context": {
                "return_url": return_url,
                "cancel_url": cancel_url,
            },
            **kwargs,
        }

        try:
            response = self.client.post(url, data=payload, headers=self._get_headers())
            authorization_url = next(
                (
                    link.get("href")
                    for link in response.get("links", [])
                    if link.get("rel") == "approve"
                ),
                None,
            )
            return {
                **response,
                "reference": response.get("id", reference),
                "authorization_url": authorization_url,
            }
        except PaymentError:
            raise
        except Exception as e:
            raise ProviderError(f"Failed to initialize payment: {e}") from e

    def verify_payment(self, reference: str) -> Dict[str, Any]:
        """
        Verify (and, if needed, capture) an order.

        `reference` is the PayPal Order id. If the order is APPROVED
        (customer has authorized it but funds haven't been captured
        yet), this captures it — PayPal payments don't complete on
        their own the way the other providers' do.
        """
        url = f"{self.base_url}/v2/checkout/orders/{reference}"
        try:
            response = self.client.get(url, headers=self._get_headers())
            status = response.get("status")

            if status == "APPROVED":
                capture_url = f"{url}/capture"
                response = self.client.post(
                    capture_url, data={}, headers=self._get_headers()
                )
                status = response.get("status")

            if status == "COMPLETED":
                normalized = "success"
            elif status in ("CREATED", "SAVED", "PAYER_ACTION_REQUIRED"):
                normalized = "pending"
            else:
                normalized = "failed"

            return {**response, "reference": reference, "status": normalized}
        except PaymentError:
            raise
        except Exception as e:
            raise ProviderError(f"Failed to verify payment: {e}") from e

    def refund_payment(
        self, reference: str, amount: Optional[int] = None, **kwargs: Any
    ) -> Dict[str, Any]:
        """
        Refund a captured order, in full or in part.

        Resolves `reference` (an Order id) to its capture id first
        (one extra request) — PayPal refunds are keyed by capture id,
        not order id.
        """
        try:
            order = self.client.get(
                f"{self.base_url}/v2/checkout/orders/{reference}",
                headers=self._get_headers(),
            )
            purchase_units = order.get("purchase_units", [])
            captures = (
                purchase_units[0].get("payments", {}).get("captures", [])
                if purchase_units
                else []
            )
            if not captures:
                raise ProviderError(
                    f"Order {reference!r} has no capture to refund "
                    "— has it been captured?"
                )
            capture_id = captures[0]["id"]

            payload: Dict[str, Any] = dict(kwargs)
            if amount is not None:
                currency = purchase_units[0]["amount"]["currency_code"]
                payload["amount"] = {
                    "value": _format_amount(amount, currency),
                    "currency_code": currency,
                }

            response = self.client.post(
                f"{self.base_url}/v2/payments/captures/{capture_id}/refund",
                data=payload,
                headers=self._get_headers(),
            )
            return {**response, "reference": response.get("id")}
        except PaymentError:
            raise
        except Exception as e:
            raise ProviderError(f"Failed to refund payment: {e}") from e

    def verify_webhook_signature(self, payload: bytes, signature: str) -> bool:
        """
        Verify a PayPal webhook, via PayPal's own verify-webhook-signature
        API (unlike every other provider here, there's no local HMAC to
        compute — PayPal requires calling back to their API).

        Unlike other providers, `signature` here is not a single header
        value — PayPal needs several. Pass it as a JSON object of the
        request headers:

            signature = json.dumps({
                "transmission_id": request.headers["PAYPAL-TRANSMISSION-ID"],
                "transmission_time": request.headers["PAYPAL-TRANSMISSION-TIME"],
                "cert_url": request.headers["PAYPAL-CERT-URL"],
                "auth_algo": request.headers["PAYPAL-AUTH-ALGO"],
                "transmission_sig": request.headers["PAYPAL-TRANSMISSION-SIG"],
            })

        Requires `webhook_secret` in Config — for PayPal this holds
        your Webhook ID (from the PayPal developer dashboard), not a
        signing secret.
        """
        if not self.config.webhook_secret:
            raise ConfigurationError(
                "webhook_secret (PayPal Webhook ID) is required to verify "
                "PayPal webhooks"
            )

        try:
            headers_data = json.loads(signature)
        except (TypeError, ValueError):
            return False
        try:
            webhook_event = json.loads(payload)
        except ValueError:
            return False

        body = {
            "transmission_id": headers_data.get("transmission_id"),
            "transmission_time": headers_data.get("transmission_time"),
            "cert_url": headers_data.get("cert_url"),
            "auth_algo": headers_data.get("auth_algo"),
            "transmission_sig": headers_data.get("transmission_sig"),
            "webhook_id": self.config.webhook_secret,
            "webhook_event": webhook_event,
        }

        try:
            response = self.client.post(
                f"{self.base_url}/v1/notifications/verify-webhook-signature",
                data=body,
                headers=self._get_headers(),
            )
        except PaymentError:
            return False
        except Exception:
            return False
        return response.get("verification_status") == "SUCCESS"
