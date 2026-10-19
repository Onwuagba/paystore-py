"""Extract normalized fields from a provider's verify_payment response."""

from typing import Any, Dict

from paystore.utils.currency import from_decimal_string


def _id(value: Any) -> Any:
    return value.get("id") if isinstance(value, dict) else value


def extract_payment_fields(provider: str, raw: Dict[str, Any]) -> Dict[str, Any]:
    provider = provider.lower()
    if provider == "stripe":  # a Checkout Session
        currency = raw.get("currency")
        return {
            "amount": raw.get("amount_total"),
            "currency": currency.upper() if currency else None,
            "customer_id": _id(raw.get("customer")),
            "subscription_id": _id(raw.get("subscription")),
        }
    if provider == "paystack":
        nested = raw.get("data")
        data: Dict[str, Any] = nested if isinstance(nested, dict) else raw
        customer = data.get("customer") or {}
        return {
            "amount": data.get("amount"),
            "currency": data.get("currency"),
            "customer_id": customer.get("customer_code"),
        }
    if provider == "paypal":  # an Order
        units = raw.get("purchase_units") or []
        amount = (units[0].get("amount") if units else None) or {}
        currency = amount.get("currency_code")
        value = amount.get("value")
        return {
            "amount": from_decimal_string(value, currency)
            if value and currency
            else None,
            "currency": currency,
        }
    return {}
