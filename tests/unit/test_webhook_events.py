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
