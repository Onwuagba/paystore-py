"""Normalize provider invoice/billing-attempt objects into models.Invoice."""

from typing import Any, Dict, Optional

from paystore.core.models import Invoice, InvoiceStatus
from paystore.core.subscriptions import parse_datetime
from paystore.utils.currency import from_decimal_string

_I = InvoiceStatus

_STRIPE_STATUS = {
    "draft": _I.DRAFT,
    "open": _I.OPEN,
    "paid": _I.PAID,
    "uncollectible": _I.UNCOLLECTIBLE,
    "void": _I.VOID,
}


def _stripe(raw: Dict[str, Any]) -> Invoice:
    currency = raw.get("currency")
    # Newer API versions nest the subscription under parent.subscription_details.
    parent = (raw.get("parent") or {}).get("subscription_details") or {}
    subscription = raw.get("subscription") or parent.get("subscription")
    customer = raw.get("customer")
    return Invoice(
        id=str(raw.get("id", "")),
        provider="stripe",
        number=raw.get("number"),
        status=_STRIPE_STATUS.get(str(raw.get("status")), _I.UNKNOWN),
        amount_due=raw.get("amount_due"),
        amount_paid=raw.get("amount_paid"),
        currency=currency.upper() if currency else None,
        hosted_url=raw.get("hosted_invoice_url"),
        pdf_url=raw.get("invoice_pdf"),
        subscription_id=(
            subscription.get("id") if isinstance(subscription, dict) else subscription
        ),
        customer_id=customer.get("id") if isinstance(customer, dict) else customer,
        attempt_count=raw.get("attempt_count"),
        next_attempt_at=parse_datetime(raw.get("next_payment_attempt")),
        created_at=parse_datetime(raw.get("created")),
        raw=raw,
    )


def _paypal(raw: Dict[str, Any]) -> Invoice:
    """
    Handles both PayPal shapes a billing event can carry: a completed
    sale (PAYMENT.SALE.COMPLETED) or a subscription whose last payment
    failed (BILLING.SUBSCRIPTION.PAYMENT.FAILED).
    """
    failed = (raw.get("billing_info") or {}).get("last_failed_payment")
    if failed:
        amount = failed.get("amount") or {}
        currency = amount.get("currency_code")
        value = amount.get("value")
        due = from_decimal_string(value, currency) if value and currency else None
        return Invoice(
            id=f"{raw.get('id', '')}:{failed.get('time', '')}",
            provider="paypal",
            status=_I.FAILED,
            amount_due=due,
            amount_paid=0,
            currency=currency,
            subscription_id=raw.get("id"),
            customer_id=(raw.get("subscriber") or {}).get("payer_id"),
            attempt_count=(raw.get("billing_info") or {}).get("failed_payments_count"),
            created_at=parse_datetime(failed.get("time")),
            raw=raw,
        )
    amount = raw.get("amount") or {}
    currency = amount.get("currency")
    total = amount.get("total")
    paid = from_decimal_string(total, currency) if total and currency else None
    completed = str(raw.get("state")).lower() == "completed"
    return Invoice(
        id=str(raw.get("id", "")),
        provider="paypal",
        status=_I.PAID if completed else _I.UNKNOWN,
        amount_due=paid,
        amount_paid=paid if completed else 0,
        currency=currency,
        subscription_id=raw.get("billing_agreement_id"),
        created_at=parse_datetime(raw.get("create_time")),
        raw=raw,
    )


def _paystack(raw: Dict[str, Any]) -> Invoice:
    subscription = raw.get("subscription") or {}
    customer = raw.get("customer") or {}
    paid = bool(raw.get("paid"))
    amount: Optional[int] = raw.get("amount")
    status = (
        _I.PAID if paid else (_I.FAILED if raw.get("status") == "failed" else _I.OPEN)
    )
    return Invoice(
        id=str(raw.get("invoice_code", raw.get("id", ""))),
        provider="paystack",
        status=status,
        amount_due=amount,
        amount_paid=amount if paid else 0,
        currency=raw.get("currency"),
        subscription_id=subscription.get("subscription_code"),
        customer_id=customer.get("customer_code"),
        created_at=parse_datetime(raw.get("created_at")),
        raw=raw,
    )


_PARSERS = {"stripe": _stripe, "paypal": _paypal, "paystack": _paystack}


def parse_invoice(provider: str, raw: Dict[str, Any]) -> Invoice:
    """Build an Invoice from a provider object; ValueError if unsupported."""
    parser = _PARSERS.get(provider.lower())
    if parser is None:
        raise ValueError(f"No invoice parser for provider {provider!r}")
    return parser(raw)
