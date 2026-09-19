#!/usr/bin/env python3
"""
Smoke test against real provider sandboxes.

Run this manually — it is NOT part of the pytest suite because it makes
real network calls to each provider's sandbox API. It never moves money:
it only calls initialize_payment (creates a pending, unpaid transaction),
verify_payment (read-only), and create_customer where implemented. It
never calls charge_authorization, since that needs a real saved-card
token you can only get from a completed payment.

Refuses to run against anything that looks like a live/production key —
sandbox keys only.

Usage:
    export PAYSTACK_SECRET_KEY=sk_test_...
    export FLUTTERWAVE_SECRET_KEY=FLWSECK_TEST-...
    export STRIPE_SECRET_KEY=sk_test_...
    export REMITA_SECRET_KEY=...
    export REMITA_API_SECRET=...
    export REMITA_MERCHANT_ID=...
    export REMITA_SERVICE_TYPE_ID=...

    python scripts/smoke_test.py

Only providers whose env vars are set are tested; the rest are skipped,
not failed. Exits non-zero if any tested provider fails.
"""

import os
import sys
from typing import Any, Callable, Dict, Optional

from paystore import Gateway
from paystore.core.exceptions import PaymentError

TEST_EMAIL = "smoke-test@example.com"
TEST_AMOUNT_MINOR_UNITS = 1000  # smallest currency unit: kobo/cents

# Prefixes that mean "this is a live key" for providers where the
# convention is documented. Remita has no well-known prefix convention,
# so it isn't checked — double-check you're using sandbox credentials.
LIVE_KEY_PREFIXES = {
    "paystack": "sk_live_",
    "stripe": "sk_live_",
    "flutterwave": "FLWSECK-",
}


def _color(code: str, text: str) -> str:
    return f"\033[{code}m{text}\033[0m" if sys.stdout.isatty() else text


def _ok(text: str) -> str:
    return _color("32", text)


def _fail(text: str) -> str:
    return _color("31", text)


def _skip(text: str) -> str:
    return _color("33", text)


def _bold(text: str) -> str:
    return _color("1", text)


PROVIDERS = [
    {"name": "paystack", "env_key": "PAYSTACK_SECRET_KEY", "currency": "NGN"},
    {"name": "flutterwave", "env_key": "FLUTTERWAVE_SECRET_KEY", "currency": "NGN"},
    {"name": "stripe", "env_key": "STRIPE_SECRET_KEY", "currency": "USD"},
    {"name": "remita", "env_key": "REMITA_SECRET_KEY", "currency": "NGN"},
]


def _remita_extra_kwargs() -> Dict[str, Optional[str]]:
    return {
        "api_secret": os.getenv("REMITA_API_SECRET"),
        "merchant_id": os.getenv("REMITA_MERCHANT_ID"),
        "service_type_id": os.getenv("REMITA_SERVICE_TYPE_ID"),
        "payer_phone": os.getenv("REMITA_TEST_PHONE", "08000000000"),
    }


EXTRA_KWARGS: Dict[str, Callable[[], Dict[str, Any]]] = {
    "remita": _remita_extra_kwargs,
}


def _report_exception(step: str, e: Exception, expected: bool = False) -> None:
    label = "FAIL" if not expected else "OK"
    prefix = _fail(label) if not expected else _ok(label)
    kind = type(e).__name__ if expected else f"unexpected {type(e).__name__}"
    print(f"  {prefix}    {step} raised {kind}: {e}")


def _check_initialize(gateway: Gateway, currency: str) -> "tuple[bool, Optional[str]]":
    try:
        transaction = gateway.payments.initialize(
            amount=TEST_AMOUNT_MINOR_UNITS, email=TEST_EMAIL, currency=currency
        )
    except PaymentError as e:
        _report_exception("initialize_payment", e, expected=True)
        return False, None
    except Exception as e:
        _report_exception("initialize_payment", e)
        return False, None

    reference = transaction.get("reference")
    auth_url = transaction.get("authorization_url")
    if reference and auth_url:
        print(f"  {_ok('OK')}    initialize_payment -> reference={reference!r}")
        print(f"          authorization_url={auth_url}")
        return True, reference

    print(f"  {_fail('FAIL')}  initialize_payment: missing reference/authorization_url")
    print(f"          raw response: {transaction}")
    return False, reference


def _check_verify(gateway: Gateway, reference: str) -> bool:
    try:
        result = gateway.payments.verify(reference)
    except PaymentError as e:
        _report_exception("verify_payment", e, expected=True)
        return False
    except Exception as e:
        _report_exception("verify_payment", e)
        return False

    status = result.get("status")
    print(
        f"  {_ok('OK')}    verify_payment -> status={status!r} "
        "(unpaid, so pending/failed here is expected)"
    )
    return True


def _check_create_customer(gateway: Gateway, name: str) -> bool:
    try:
        customer = gateway.customers.create(
            email=TEST_EMAIL, first_name="Smoke", last_name="Test"
        )
    except NotImplementedError:
        print(f"  {_skip('SKIP')}  create_customer: not implemented for {name}")
        return True
    except PaymentError as e:
        _report_exception("create_customer", e, expected=True)
        return False
    except Exception as e:
        _report_exception("create_customer", e)
        return False

    customer_code = customer.get("customer_code")
    if customer_code:
        print(f"  {_ok('OK')}    create_customer -> customer_code={customer_code!r}")
        return True

    print(f"  {_fail('FAIL')}  create_customer: missing customer_code")
    print(f"          raw response: {customer}")
    return False


def run_provider(spec: Dict[str, str]) -> Optional[bool]:
    name = spec["name"]
    api_key = os.getenv(spec["env_key"])
    if not api_key:
        print(f"{_skip('SKIP')}  {name}: {spec['env_key']} not set")
        return None

    live_prefix = LIVE_KEY_PREFIXES.get(name)
    if live_prefix and api_key.startswith(live_prefix):
        print(
            f"{_fail('REFUSED')}  {name}: {spec['env_key']} looks like a LIVE key "
            f"(starts with {live_prefix!r}). Use a sandbox/test key."
        )
        return False

    extra = EXTRA_KWARGS.get(name, dict)()
    missing = [k for k, v in extra.items() if k != "payer_phone" and not v]
    if missing:
        print(f"{_skip('SKIP')}  {name}: missing {', '.join(missing)}")
        return None

    print(f"\n{_bold(name.upper())}")
    try:
        gateway = Gateway(
            provider=name, api_key=api_key, environment="sandbox", **extra
        )
    except Exception as e:
        print(f"  {_fail('FAIL')}  could not build Gateway: {type(e).__name__}: {e}")
        return False

    init_ok, reference = _check_initialize(gateway, spec["currency"])
    verify_ok = _check_verify(gateway, reference) if reference else True
    customer_ok = _check_create_customer(gateway, name)

    return init_ok and verify_ok and customer_ok


def main() -> int:
    print(_bold("paystore smoke test") + " -- hits real sandbox APIs, no money moves.")
    results = [run_provider(spec) for spec in PROVIDERS]
    tested = [r for r in results if r is not None]

    print("\n" + _bold("Summary"))
    if not tested:
        print(_skip("No providers tested -- set at least one *_SECRET_KEY env var."))
        return 0

    passed = sum(1 for r in tested if r)
    print(f"{passed}/{len(tested)} providers passed")
    return 0 if all(tested) else 1


if __name__ == "__main__":
    sys.exit(main())
