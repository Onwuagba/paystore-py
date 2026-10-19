"""Tests for invoices, richer payments, capabilities, and new webhook mappings."""

from paystore.core.gateway import Gateway
from paystore.core.invoices import parse_invoice
from paystore.core.models import InvoiceStatus, Payment, PaymentStatus
from paystore.webhooks.events import WebhookEvent

STRIPE_INVOICE = {
    "id": "in_1",
    "number": "INV-0001",
    "status": "open",
    "amount_due": 5000,
    "amount_paid": 0,
    "currency": "usd",
    "hosted_invoice_url": "https://invoice.stripe.com/i/x",
    "invoice_pdf": "https://pay.stripe.com/x.pdf",
    "customer": "cus_1",
    "subscription": "sub_1",
    "attempt_count": 2,
    "next_payment_attempt": 1700000000,
    "created": 1690000000,
}


def test_stripe_invoice_fields():
    inv = parse_invoice("stripe", STRIPE_INVOICE)
    assert inv.status is InvoiceStatus.OPEN
    assert (inv.number, inv.amount_due, inv.currency) == ("INV-0001", 5000, "USD")
    assert inv.hosted_url.startswith("https://invoice") and inv.pdf_url.endswith(".pdf")
    assert (inv.subscription_id, inv.customer_id, inv.attempt_count) == (
        "sub_1",
        "cus_1",
        2,
    )
    assert inv.next_attempt_at.year == 2023


def test_stripe_invoice_new_api_subscription_location():
    raw = {"id": "in_2", "parent": {"subscription_details": {"subscription": "sub_9"}}}
    assert parse_invoice("stripe", raw).subscription_id == "sub_9"


def test_paypal_failed_payment_becomes_failed_invoice():
    raw = {
        "id": "I-1",
        "subscriber": {"payer_id": "P"},
        "billing_info": {
            "failed_payments_count": 2,
            "last_failed_payment": {
                "amount": {"currency_code": "USD", "value": "10.00"},
                "time": "2026-10-01T10:00:00Z",
            },
        },
    }
    inv = parse_invoice("paypal", raw)
    assert inv.status is InvoiceStatus.FAILED
    assert (inv.amount_due, inv.currency, inv.attempt_count) == (1000, "USD", 2)
    assert inv.subscription_id == "I-1"


def test_paypal_sale_completed_is_paid_invoice():
    raw = {
        "id": "SALE_1",
        "state": "completed",
        "amount": {"total": "10.00", "currency": "USD"},
        "billing_agreement_id": "I-1",
    }
    inv = parse_invoice("paypal", raw)
    assert inv.status is InvoiceStatus.PAID and inv.amount_paid == 1000


def test_paystack_invoice():
    inv = parse_invoice(
        "paystack",
        {
            "invoice_code": "INV_1",
            "paid": True,
            "amount": 5000,
            "subscription": {"subscription_code": "SUB_1"},
        },
    )
    assert inv.status is InvoiceStatus.PAID and inv.subscription_id == "SUB_1"


def test_webhook_invoice_and_trial_will_end():
    event = WebhookEvent.from_raw(
        "stripe",
        {
            "id": "e",
            "type": "invoice.payment_failed",
            "data": {"object": STRIPE_INVOICE},
        },
    )
    assert event.type == "invoice.payment_failed" and event.invoice.attempt_count == 2

    trial = WebhookEvent.from_raw(
        "stripe",
        {
            "type": "customer.subscription.trial_will_end",
            "data": {"object": {"id": "sub_1", "status": "trialing"}},
        },
    )
    assert trial.type == "subscription.trial_will_end"
    assert trial.subscription.status.value == "trialing"


def test_more_event_mappings():
    for provider, name, expected in [
        ("stripe", "customer.subscription.paused", "subscription.paused"),
        ("stripe", "customer.subscription.resumed", "subscription.resumed"),
        ("stripe", "invoice.upcoming", "invoice.upcoming"),
        ("stripe", "invoice.payment_succeeded", "invoice.paid"),
        (
            "stripe",
            "invoice.payment_action_required",
            "invoice.payment_action_required",
        ),
        ("stripe", "checkout.session.expired", "checkout.expired"),
        ("stripe", "charge.dispute.created", "dispute.created"),
        ("paystack", "invoice.create", "invoice.created"),
        ("paypal", "BILLING.SUBSCRIPTION.SUSPENDED", "subscription.paused"),
    ]:
        key = (
            "event_type"
            if provider == "paypal"
            else ("type" if provider == "stripe" else "event")
        )
        assert WebhookEvent.from_raw(provider, {key: name, "data": {}}).type == expected


def test_payment_fields_stripe_session_and_paypal_order():
    stripe = Payment.from_raw(
        "stripe",
        {
            "reference": "cs_1",
            "status": "success",
            "amount_total": 5000,
            "currency": "usd",
            "customer": "cus_1",
            "subscription": "sub_1",
        },
    )
    assert stripe.status is PaymentStatus.SUCCESS
    assert (stripe.amount, stripe.currency, stripe.subscription_id) == (
        5000,
        "USD",
        "sub_1",
    )

    paypal = Payment.from_raw(
        "paypal",
        {
            "reference": "O1",
            "status": "success",
            "purchase_units": [{"amount": {"currency_code": "USD", "value": "10.00"}}],
        },
    )
    assert (paypal.amount, paypal.currency) == (1000, "USD")


def test_capabilities_per_provider():
    stripe = Gateway(
        provider="stripe", api_key="sk_test_x"
    ).subscriptions.capabilities()
    assert (
        stripe["cancel_at_period_end"]
        and stripe["billing_portal"]
        and stripe["reuse_product"]
    )
    paypal = Gateway(
        provider="paypal", api_key="id", api_secret="secret"
    ).subscriptions.capabilities()
    assert not paypal["cancel_at_period_end"] and not paypal["billing_portal"]
    assert paypal["quantity_change_needs_approval"] and paypal["fixed_tax_rate"]
    assert paypal["verified_live"] is False
    assert (
        Gateway(provider="paystack", api_key="sk_x").subscriptions.capabilities()[
            "resume"
        ]
        is False
    )


def test_stripe_invoice_totals_tax_and_billed_period():
    raw = {
        "id": "in_3",
        "subtotal": 5000,
        "total": 5375,
        "tax": 375,
        "period_start": 1,
        "period_end": 2,
        "lines": {"data": [{"period": {"start": 1690000000, "end": 1692592000}}]},
    }
    inv = parse_invoice("stripe", raw)
    assert (inv.subtotal, inv.tax, inv.total) == (5000, 375, 5375)
    assert inv.period_start.year == 2023  # line period, not the invoice's own


def test_stripe_invoice_tax_from_total_taxes_and_period_fallback():
    raw = {
        "id": "in_4",
        "total": 1100,
        "total_taxes": [{"amount": 60}, {"amount": 40}],
        "period_start": 1690000000,
        "period_end": 1692592000,
    }
    inv = parse_invoice("stripe", raw)
    assert inv.tax == 100 and inv.period_end.year == 2023
    assert parse_invoice("stripe", {"id": "in_5"}).tax is None


def test_paypal_sale_tax_details_and_paystack_total():
    sale = parse_invoice(
        "paypal",
        {
            "id": "S",
            "state": "completed",
            "amount": {
                "total": "10.75",
                "currency": "USD",
                "details": {"subtotal": "10.00", "tax": "0.75"},
            },
        },
    )
    assert (sale.subtotal, sale.tax, sale.total) == (1000, 75, 1075)
    assert parse_invoice("paystack", {"invoice_code": "I", "amount": 500}).total == 500
