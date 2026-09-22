"""Generic webhook views for paystore providers (sync and async)."""

import json
from typing import Any, Dict, Optional, Tuple

from django.http import HttpRequest, HttpResponse, JsonResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from paystore.core.exceptions import PaymentError
from paystore.webhooks.headers import SIGNATURE_HEADERS

from paystore_django.gateway import get_async_gateway, get_gateway
from paystore_django.signals import webhook_verified


def _to_wsgi_meta_key(header_name: str) -> str:
    """Convert a plain HTTP header name to its Django request.META key."""
    return "HTTP_" + header_name.upper().replace("-", "_")


def _extract_signature(
    request: HttpRequest, provider: str, signature_header_override: Optional[str]
) -> str:
    header_name = signature_header_override or SIGNATURE_HEADERS.get(provider.lower())
    if not header_name:
        return ""
    return request.META.get(_to_wsgi_meta_key(header_name), "")


def _parse_event_body(request: HttpRequest) -> Dict[str, Any]:
    try:
        return json.loads(request.body or b"{}")
    except ValueError:
        return {}


class _WebhookViewMixin:
    """Shared config/attributes for both the sync and async webhook views."""

    provider: Optional[str] = None  # pins this view to one provider
    # Plain header name override, e.g. "X-Foo-Signature"
    signature_header: Optional[str] = None

    def handle_event(self, event: Dict[str, Any], request: HttpRequest) -> None:
        """Override to react to a verified webhook event."""


@method_decorator(csrf_exempt, name="dispatch")
class PaystoreWebhookView(_WebhookViewMixin, View):
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

    See PaystoreAsyncWebhookView for an async equivalent.
    """

    def post(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        gateway = get_gateway(self.provider)
        signature = _extract_signature(
            request, gateway.config.provider, self.signature_header
        )

        try:
            gateway.verify_webhook(request.body, signature)
        except PaymentError:
            return HttpResponse(status=400)

        event = _parse_event_body(request)
        webhook_verified.send(
            sender=self.__class__, provider=gateway.config.provider, event=event
        )
        self.handle_event(event, request)
        return JsonResponse({"received": True})


@method_decorator(csrf_exempt, name="dispatch")
class PaystoreAsyncWebhookView(_WebhookViewMixin, View):
    """
    Async equivalent of PaystoreWebhookView, backed by AsyncGateway — for
    Django's async views (`async def post`, ASGI deployment).

    Usage is identical to PaystoreWebhookView except `handle_event` may
    be a coroutine function (awaited if so) or a plain function:

        class PaystackWebhookView(PaystoreAsyncWebhookView):
            provider = "paystack"

            async def handle_event(self, event, request):
                await Order.objects.filter(...).aupdate(paid=True)
    """

    async def post(
        self, request: HttpRequest, *args: Any, **kwargs: Any
    ) -> HttpResponse:
        gateway = get_async_gateway(self.provider)
        provider, signature = self._resolve_provider_and_signature(request, gateway)

        try:
            await gateway.verify_webhook(request.body, signature)
        except PaymentError:
            return HttpResponse(status=400)

        event = _parse_event_body(request)
        webhook_verified.send(sender=self.__class__, provider=provider, event=event)

        result = self.handle_event(event, request)
        if hasattr(result, "__await__"):
            await result
        return JsonResponse({"received": True})

    def _resolve_provider_and_signature(
        self, request: HttpRequest, gateway: Any
    ) -> Tuple[str, str]:
        provider = gateway.config.provider
        signature = _extract_signature(request, provider, self.signature_header)
        return provider, signature
