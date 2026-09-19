"""Generic webhook view for paystore providers."""

import json
from typing import Any, Dict, Optional

from django.http import HttpRequest, HttpResponse, JsonResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from paystore.core.exceptions import PaymentError

from paystore_django.gateway import get_gateway
from paystore_django.signals import webhook_verified

# Provider name -> raw signature header, as it appears in request.META
# (WSGI uppercases and prefixes custom headers with HTTP_).
SIGNATURE_HEADERS = {
    "paystack": "HTTP_X_PAYSTACK_SIGNATURE",
    "flutterwave": "HTTP_VERIF_HASH",
    "stripe": "HTTP_STRIPE_SIGNATURE",
    "remita": "HTTP_X_REMITA_SIGNATURE",
}


@method_decorator(csrf_exempt, name="dispatch")
class PaystoreWebhookView(View):
    """
    Verifies a provider's webhook signature, then calls `handle_event`.

    Subclass and override `handle_event` for your business logic (e.g.
    marking an order paid), or connect to the `webhook_verified` signal
    instead if you'd rather not subclass.

    Usage:
        class PaystackWebhookView(PaystoreWebhookView):
            provider = "paystack"

            def handle_event(self, event, request):
                if event.get("event") == "charge.success":
                    ...

        urlpatterns = [path("webhooks/paystack/", PaystackWebhookView.as_view())]
    """

    provider: Optional[str] = None  # pins this view to one provider
    signature_header: Optional[str] = None  # override for a nonstandard header

    def post(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        gateway = get_gateway(self.provider)
        header_name = self.signature_header or SIGNATURE_HEADERS.get(
            gateway.config.provider.lower()
        )
        signature = request.META.get(header_name, "") if header_name else ""

        try:
            gateway.verify_webhook(request.body, signature)
        except PaymentError:
            return HttpResponse(status=400)

        try:
            event: Dict[str, Any] = json.loads(request.body or b"{}")
        except ValueError:
            event = {}

        webhook_verified.send(
            sender=self.__class__, provider=gateway.config.provider, event=event
        )
        self.handle_event(event, request)
        return JsonResponse({"received": True})

    def handle_event(self, event: Dict[str, Any], request: HttpRequest) -> None:
        """Override to react to a verified webhook event."""
