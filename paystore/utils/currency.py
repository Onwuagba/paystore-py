"""Currency-related helpers.

Every provider in this library treats `amount` as already being in the
currency's smallest unit (e.g. kobo, cents) — consistent with Paystack/
Flutterwave/Remita's convention for NGN. Most currencies have 2 decimal
places, so "smallest unit" means "major unit * 100". A handful of
currencies (Stripe's docs call these "zero-decimal currencies") have no
subdivision at all — for these, the smallest unit *is* the major unit,
and multiplying by 100 would charge 100x too much.

This mostly matters for Stripe, since Paystack/Flutterwave/Remita are
Nigeria-focused and only really used with NGN in practice.
"""

# https://docs.stripe.com/currencies#zero-decimal
ZERO_DECIMAL_CURRENCIES = frozenset(
    {
        "BIF",
        "CLP",
        "DJF",
        "GNF",
        "JPY",
        "KMF",
        "KRW",
        "MGA",
        "PYG",
        "RWF",
        "UGX",
        "VND",
        "VUV",
        "XAF",
        "XOF",
        "XPF",
    }
)


def is_zero_decimal_currency(currency: str) -> bool:
    """
    Check whether a currency has no minor unit (e.g. JPY, KRW).

    For these currencies, pass the amount as-is (e.g. 500 for ¥500) —
    do NOT multiply by 100 the way you would for NGN/USD-style amounts.
    """
    return currency.upper() in ZERO_DECIMAL_CURRENCIES


def to_decimal_string(amount: int, currency: str) -> str:
    """
    Convert a minor-unit int amount to a decimal-string major-unit
    amount, for providers (PayPal, MTN MoMo) whose API wants "10.00"
    instead of 1000 — zero-decimal-currency aware, same as
    is_zero_decimal_currency.
    """
    if is_zero_decimal_currency(currency):
        return str(amount)
    return f"{amount / 100:.2f}"
