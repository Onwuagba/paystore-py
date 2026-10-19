"""Tests for WebhookEvent normalization."""

from paystore.webhooks.events import WebhookEvent


def test_paystack_event_normalizes_event_and_data():
    raw = {
        "event": "charge.success",
        "data": {"reference": "TXN_1", "status": "success"},
    }
    event = WebhookEvent.from_raw("paystack", raw)
    assert event.event_type == "charge.success"
    assert event.data == {"reference": "TXN_1", "status": "success"}
    assert event.raw == raw


def test_flutterwave_event_normalizes_event_and_data():
    raw = {
        "event": "charge.completed",
        "data": {"tx_ref": "TXN_1", "status": "successful"},
    }
    event = WebhookEvent.from_raw("flutterwave", raw)
    assert event.event_type == "charge.completed"
    assert event.data == {"tx_ref": "TXN_1", "status": "successful"}


def test_stripe_event_unwraps_data_object():
    raw = {
        "type": "checkout.session.completed",
        "data": {"object": {"id": "cs_test_1", "payment_status": "paid"}},
    }
    event = WebhookEvent.from_raw("stripe", raw)
    assert event.event_type == "checkout.session.completed"
    assert event.data == {"id": "cs_test_1", "payment_status": "paid"}


def test_remita_event_falls_back_to_unknown_type_and_raw_as_data():
    raw = {"status": "00", "orderId": "TXN_1"}
    event = WebhookEvent.from_raw("remita", raw)
    assert event.event_type == "unknown"
    assert event.data == raw
    assert event.raw == raw


def test_provider_name_is_lowercased():
    event = WebhookEvent.from_raw("PAYSTACK", {"event": "charge.success", "data": {}})
    assert event.provider == "paystack"


def test_missing_data_key_falls_back_to_raw():
    raw = {"event": "charge.success"}
    event = WebhookEvent.from_raw("paystack", raw)
    assert event.data == raw


def test_stripe_event_has_canonical_type_id_and_timestamp():
    raw = {
        "id": "evt_1",
        "created": 1700000000,
        "type": "customer.subscription.updated",
        "data": {
            "object": {
                "id": "sub_1",
                "status": "past_due",
                "items": {"data": [{"quantity": 2, "price": {"id": "price_1"}}]},
            }
        },
    }
    event = WebhookEvent.from_raw("stripe", raw)
    assert event.type == "subscription.updated"
    assert event.event_type == "customer.subscription.updated"
    assert event.id == "evt_1"
    assert event.created_at.year == 2023
    assert event.subscription.status.value == "past_due"
    assert event.subscription.quantity == 2


def test_paypal_event_uses_resource_and_event_type():
    raw = {
        "id": "WH-1",
        "create_time": "2026-10-01T10:00:00Z",
        "event_type": "BILLING.SUBSCRIPTION.CANCELLED",
        "resource": {"id": "I-1", "status": "CANCELLED", "plan_id": "P-1"},
    }
    event = WebhookEvent.from_raw("paypal", raw)
    assert event.type == "subscription.canceled"
    assert event.data["id"] == "I-1"
    assert event.id == "WH-1"
    assert event.created_at.month == 10
    assert event.subscription.status.value == "canceled"


def test_paypal_payment_capture_completed():
    raw = {"event_type": "PAYMENT.CAPTURE.COMPLETED", "resource": {"id": "CAP_1"}}
    event = WebhookEvent.from_raw("paypal", raw)
    assert event.type == "payment.succeeded"
    assert event.subscription is None


def test_flutterwave_failed_charge_is_payment_failed():
    raw = {"event": "charge.completed", "data": {"status": "failed"}}
    assert WebhookEvent.from_raw("flutterwave", raw).type == "payment.failed"


def test_paystack_charge_success_canonical_and_no_id():
    event = WebhookEvent.from_raw("paystack", {"event": "charge.success", "data": {}})
    assert event.type == "payment.succeeded"
    assert event.id is None and event.created_at is None


def test_unmapped_event_is_unknown_type():
    event = WebhookEvent.from_raw("stripe", {"type": "balance.available", "data": {}})
    assert event.type == "unknown"
    assert event.event_type == "balance.available"
