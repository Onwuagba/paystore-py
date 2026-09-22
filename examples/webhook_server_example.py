#!/usr/bin/env python3
"""
Webhook Server Example - verify and handle provider webhooks.

Uses only the standard library (no Flask/FastAPI) so it runs anywhere.
Paystore's paystore-django package has an equivalent for Django
projects (paystore_django.PaystoreWebhookView).

Before running:
    export PAYMENT_PROVIDER=paystack   # or flutterwave / stripe / remita
    export PAYSTACK_SECRET_KEY=sk_test_your_key
    # Stripe/Flutterwave also need a webhook secret to verify signatures:
    export PAYSTACK_WEBHOOK_SECRET=...  # ({PROVIDER}_WEBHOOK_SECRET)

Then expose this to the internet (e.g. `ngrok http 8000`) and register
the public URL + path in your provider's dashboard as the webhook
endpoint. Stripe users can skip the tunnel/dashboard step entirely with
the Stripe CLI: `stripe listen --forward-to localhost:8000/webhook`.

    python examples/webhook_server_example.py
"""

import json
import os
from http.server import BaseHTTPRequestHandler, HTTPServer

from paystore import Gateway
from paystore.core.exceptions import PaymentError
from paystore.webhooks.headers import SIGNATURE_HEADERS


def handle_verified_event(event: dict) -> None:
    """
    Your business logic goes here — this is called only after the
    signature has been verified, so `event` can be trusted.
    """
    print(f"✓ Verified webhook event: {event}")
    # e.g.: look up the order by event["data"]["reference"] and mark it paid


class WebhookHandler(BaseHTTPRequestHandler):
    gateway: Gateway  # set in main() before the server starts

    def do_POST(self) -> None:
        content_length = int(self.headers.get("Content-Length", 0))
        payload = self.rfile.read(content_length)

        provider = self.gateway.config.provider
        signature_header = SIGNATURE_HEADERS.get(provider, "")
        signature = self.headers.get(signature_header, "")

        try:
            self.gateway.verify_webhook(payload, signature)
        except PaymentError:
            print("✗ Rejected webhook: invalid signature")
            self.send_response(400)
            self.end_headers()
            return

        try:
            event = json.loads(payload or b"{}")
        except ValueError:
            event = {}

        handle_verified_event(event)

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"received": true}')

    def log_message(self, format: str, *args) -> None:
        pass  # quiet default access logging; we print our own messages


def main() -> None:
    provider = os.getenv("PAYMENT_PROVIDER", "paystack")
    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "8000"))

    WebhookHandler.gateway = Gateway(provider=provider)  # reads {PROVIDER}_SECRET_KEY

    print(f"Webhook server for '{provider}' listening on http://{host}:{port}")
    print("Expose this with a tunnel (ngrok, the Stripe CLI, etc.) and register")
    print("the public URL as your webhook endpoint in the provider's dashboard.\n")

    HTTPServer((host, port), WebhookHandler).serve_forever()


if __name__ == "__main__":
    main()
