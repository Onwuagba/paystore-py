"""Tests for PaystoreWebhookView."""

import hashlib
import hmac
import json

import pytest
from django.test import RequestFactory

from paystore_django.signals import webhook_verified
from paystore_django.views import PaystoreWebhookView


@pytest.fixture
def factory():
    return RequestFactory()


class _RecordingWebhookView(PaystoreWebhookView):
    provider = "paystack"
    received_events = []

    def handle_event(self, event, request):
        self.received_events.append(event)


@pytest.fixture(autouse=True)
def _clear_recorded_events():
    _RecordingWebhookView.received_events.clear()
    yield
    _RecordingWebhookView.received_events.clear()


def _paystack_signature(body: bytes) -> str:
    return hmac.new(b"sk_test_mock", body, hashlib.sha512).hexdigest()


def test_post_calls_handle_event_for_valid_signature(factory):
    body = json.dumps({"event": "charge.success"}).encode()
    request = factory.post(
        "/webhooks/paystack/",
        data=body,
        content_type="application/json",
        HTTP_X_PAYSTACK_SIGNATURE=_paystack_signature(body),
    )
    response = _RecordingWebhookView.as_view()(request)
    assert response.status_code == 200
    assert _RecordingWebhookView.received_events == [{"event": "charge.success"}]


def test_post_rejects_invalid_signature(factory):
    body = json.dumps({"event": "charge.success"}).encode()
    request = factory.post(
        "/webhooks/paystack/",
        data=body,
        content_type="application/json",
        HTTP_X_PAYSTACK_SIGNATURE="bad-signature",
    )
    response = _RecordingWebhookView.as_view()(request)
    assert response.status_code == 400
    assert _RecordingWebhookView.received_events == []


def test_post_sends_webhook_verified_signal(factory):
    body = json.dumps({"event": "charge.success"}).encode()
    request = factory.post(
        "/webhooks/paystack/",
        data=body,
        content_type="application/json",
        HTTP_X_PAYSTACK_SIGNATURE=_paystack_signature(body),
    )

    received = []

    def receiver(sender, provider, event, **kwargs):
        received.append((provider, event))

    webhook_verified.connect(receiver)
    try:
        _RecordingWebhookView.as_view()(request)
    finally:
        webhook_verified.disconnect(receiver)

    assert received == [("paystack", {"event": "charge.success"})]
