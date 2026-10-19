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

Implemented from PayPal's published Orders v2 / Subscriptions v1 /
Webhooks docs, not verified against a live account — double-check field names/status
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
from paystore.core.models import Subscription
from paystore.core.subscriptions import parse_subscription
from paystore.utils.currency import to_decimal_string as _format_amount
from paystore.utils.helpers import generate_reference


class PaypalProvider(BaseProvider):
    """
    PayPal payment provider (Orders v2 API).

    Does not support NGN — pass a currency PayPal supports (e.g. USD).
    Beyond one-off orders, supports PayPal Subscriptions (plans,
    subscribe via an approval link, get/cancel/resume/revise quantity).
    Subscriptions are not charged off-session: the customer approves
    each subscription once at PayPal. Not implemented: PayPal's
    saved-payment-method equivalent (Vault) and payout equivalent
    (Payouts) are different enough products that force-fitting them
    into charge_authorization/transfers here would be misleading.
    """

    SANDBOX_BASE_URL = "https://api-m.sandbox.paypal.com"
    LIVE_BASE_URL = "https://api-m.paypal.com"
    SUPPORTED_FEATURES = frozenset(
        {
            "refunds",
            "subscriptions",
            "subscription_management",
            "subscription_checkout",
        }
    )
    SUBSCRIPTION_CAPABILITIES = {
        "cancel_at_period_end": False,
        "resume": True,
        "update_quantity": True,
        "quantity_change_needs_approval": True,
        "hosted_checkout": True,
        "billing_portal": False,
        "trials": True,
        "automatic_tax": False,
        "fixed_tax_rate": True,
        "reuse_product": True,
        "invoices": False,
        "verified_live": False,
    }
    _INTERVALS = {"day": "DAY", "week": "WEEK", "month": "MONTH", "year": "YEAR"}

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

    # --- Subscriptions (v1 Billing API) -------------------------------

    def _post_json(self, path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self.client.post(
            f"{self.base_url}{path}", data=payload, headers=self._get_headers()
        )

    def create_plan(
        self,
        name: str,
        amount: int,
        interval: str,
        currency: str = "NGN",
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        Create a catalog Product and a billing Plan on it.

        interval: "day", "week", "month" or "year" (same as Stripe).
        Optional kwargs: `trial_days` (a free trial cycle before billing),
        `tax_percentage` (e.g. "7.5"; added on top of the price unless
        `tax_inclusive=True`), `quantity_supported` (bool, needed for
        seat counts). Other kwargs are merged into the plan body.
        """
        paypal_interval = self._INTERVALS.get(interval.lower())
        if paypal_interval is None:
            raise ProviderError(
                f"Unsupported interval {interval!r}; use one of "
                f"{sorted(self._INTERVALS)}"
            )
        trial_days = kwargs.pop("trial_days", None)
        tax_percentage = kwargs.pop("tax_percentage", None)
        tax_inclusive = kwargs.pop("tax_inclusive", False)
        quantity_supported = kwargs.pop("quantity_supported", False)
        product_id = kwargs.pop("product_id", None)

        def cycle(unit: str, count: int, tenure: str, sequence: int, price: str):
            return {
                "frequency": {"interval_unit": unit, "interval_count": count},
                "tenure_type": tenure,
                "sequence": sequence,
                # 0 = bill forever; the trial runs exactly once.
                "total_cycles": 1 if tenure == "TRIAL" else 0,
                "pricing_scheme": {
                    "fixed_price": {"value": price, "currency_code": currency}
                },
            }

        cycles = []
        if trial_days:
            cycles.append(cycle("DAY", int(trial_days), "TRIAL", 1, "0"))
        cycles.append(
            cycle(
                paypal_interval,
                1,
                "REGULAR",
                len(cycles) + 1,
                _format_amount(amount, currency),
            )
        )

        try:
            if not product_id:
                product_id = self._post_json(
                    "/v1/catalogs/products", {"name": name, "type": "SERVICE"}
                ).get("id")
            body: Dict[str, Any] = {
                "product_id": product_id,
                "name": name,
                "billing_cycles": cycles,
                "payment_preferences": {
                    "auto_bill_outstanding": True,
                    "payment_failure_threshold": 3,
                },
                "quantity_supported": quantity_supported,
                **kwargs,
            }
            if tax_percentage is not None:
                body["taxes"] = {
                    "percentage": str(tax_percentage),
                    "inclusive": tax_inclusive,
                }
            plan = self._post_json("/v1/billing/plans", body)
            return {**plan, "plan_code": plan.get("id"), "product_id": product_id}
        except PaymentError:
            raise
        except Exception as e:
            raise ProviderError(f"Failed to create plan: {e}") from e

    def create_subscription_checkout(
        self,
        plan: str,
        email: Optional[str] = None,
        quantity: int = 1,
        return_url: str = "https://example.com/success",
        cancel_url: str = "https://example.com/cancel",
        reference: Optional[str] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        Create a subscription the customer must approve at PayPal.

        Redirect them to `authorization_url`. The subscription stays
        APPROVAL_PENDING (normalized "incomplete") until they do; poll
        get_subscription or listen for BILLING.SUBSCRIPTION.ACTIVATED.
        `quantity` needs a plan created with quantity_supported=True.
        """
        body: Dict[str, Any] = {
            "plan_id": plan,
            "quantity": str(quantity),
            "custom_id": reference,
            "application_context": {
                "return_url": return_url,
                "cancel_url": cancel_url,
                "user_action": "SUBSCRIBE_NOW",
            },
            **kwargs,
        }
        if email:
            body["subscriber"] = {"email_address": email}
        body = {k: v for k, v in body.items() if v is not None}
        try:
            response = self._post_json("/v1/billing/subscriptions", body)
            approve = next(
                (
                    link.get("href")
                    for link in response.get("links", [])
                    if link.get("rel") == "approve"
                ),
                None,
            )
            return {
                **response,
                "subscription_code": response.get("id"),
                "reference": response.get("id"),
                "authorization_url": approve,
                "normalized_status": parse_subscription(
                    "paypal", response
                ).status.value,
            }
        except PaymentError:
            raise
        except Exception as e:
            raise ProviderError(f"Failed to create subscription: {e}") from e

    def create_subscription(
        self, customer: str, plan: str, **kwargs: Any
    ) -> Dict[str, Any]:
        """
        Subscribe by approval link. PayPal has no customer objects here,
        so `customer` is the subscriber's email address.
        """
        return self.create_subscription_checkout(plan=plan, email=customer, **kwargs)

    def get_subscription(self, subscription_code: str) -> Subscription:
        """Fetch a subscription by id (e.g. "I-BW452GLLEP1G")."""
        try:
            response = self.client.get(
                f"{self.base_url}/v1/billing/subscriptions/{subscription_code}",
                headers=self._get_headers(),
            )
            return parse_subscription("paypal", response)
        except PaymentError:
            raise
        except Exception as e:
            raise ProviderError(f"Failed to get subscription: {e}") from e

    def cancel_subscription(
        self, subscription_code: str, at_period_end: bool = False, **kwargs: Any
    ) -> Dict[str, Any]:
        """
        Cancel a subscription immediately. PayPal has no
        cancel-at-period-end, so at_period_end=True raises
        NotImplementedError rather than silently cancelling early.
        """
        if at_period_end:
            raise NotImplementedError(
                "PayPal cancels subscriptions immediately; "
                "cancel-at-period-end is not supported"
            )
        reason = kwargs.pop("reason", "Cancelled by merchant")
        try:
            self._post_json(
                f"/v1/billing/subscriptions/{subscription_code}/cancel",
                {"reason": reason, **kwargs},
            )  # 204 No Content on success
            return {
                "success": True,
                "subscription_code": subscription_code,
                "normalized_status": "canceled",
            }
        except PaymentError:
            raise
        except Exception as e:
            raise ProviderError(f"Failed to cancel subscription: {e}") from e

    def resume_subscription(
        self, subscription_code: str, **kwargs: Any
    ) -> Subscription:
        """Reactivate a SUSPENDED subscription (cancelled ones can't be resumed)."""
        reason = kwargs.pop("reason", "Reactivated by merchant")
        try:
            self._post_json(
                f"/v1/billing/subscriptions/{subscription_code}/activate",
                {"reason": reason, **kwargs},
            )
            return self.get_subscription(subscription_code)
        except PaymentError:
            raise
        except Exception as e:
            raise ProviderError(f"Failed to resume subscription: {e}") from e

    def update_subscription(
        self, subscription_code: str, quantity: Optional[int] = None, **kwargs: Any
    ) -> Subscription:
        """
        Revise a subscription's seat `quantity` (plan must have
        quantity_supported=True). PayPal may require the customer to
        re-approve the change; if so the returned Subscription's
        `approval_url` is set — send the customer there.
        """
        body: Dict[str, Any] = dict(kwargs)
        if quantity is not None:
            body["quantity"] = str(quantity)
        try:
            revised = self._post_json(
                f"/v1/billing/subscriptions/{subscription_code}/revise", body
            )
            subscription = self.get_subscription(subscription_code)
            subscription.raw["revise_links"] = revised.get("links", [])
            subscription.approval_url = next(
                (
                    link.get("href")
                    for link in revised.get("links", [])
                    if link.get("rel") == "approve"
                ),
                None,
            )
            return subscription
        except PaymentError:
            raise
        except Exception as e:
            raise ProviderError(f"Failed to update subscription: {e}") from e

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
