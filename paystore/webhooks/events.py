"""Typed wrapper around a verified webhook payload."""

from dataclasses import dataclass
from typing import Any, Dict

# Provider -> the raw payload key holding the event type/name.
_EVENT_TYPE_KEYS = {
    "paystack": "event",
    "flutterwave": "event",
    "stripe": "type",
}


@dataclass(frozen=True)
class WebhookEvent:
    """
    A verified webhook event, with the event type and the relevant data
    object normalized across providers where possible.

    `raw` is always the full, unmodified parsed JSON body — fall back to
    it for anything this normalization doesn't cover, or for a provider
    (like Remita) whose payload shape isn't well-documented enough to
    normalize confidently.
    """

    provider: str
    event_type: str
    data: Dict[str, Any]
    raw: Dict[str, Any]

    @classmethod
    def from_raw(cls, provider: str, raw: Dict[str, Any]) -> "WebhookEvent":
        provider = provider.lower()
        event_type_key = _EVENT_TYPE_KEYS.get(provider)
        event_type = (
            str(raw.get(event_type_key, "unknown")) if event_type_key else "unknown"
        )

        data = raw.get("data", raw)
        # Stripe nests the actual object one level deeper, under data.object.
        if provider == "stripe" and isinstance(data, dict) and "object" in data:
            data = data["object"]
        if not isinstance(data, dict):
            data = {}

        return cls(provider=provider, event_type=event_type, data=data, raw=raw)
