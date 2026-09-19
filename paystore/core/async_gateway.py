"""Async-friendly wrapper around Gateway."""

import asyncio
from functools import partial
from typing import Any, Dict, List, Optional

from paystore.core.config import Config
from paystore.core.gateway import Gateway


async def _run_sync(func: Any, *args: Any, **kwargs: Any) -> Any:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, partial(func, *args, **kwargs))


class AsyncGateway:
    """
    Async-friendly wrapper around Gateway, for FastAPI/async Django views.

    This runs each call in a thread pool executor rather than making a
    native non-blocking HTTP request — paystore's providers use a
    synchronous httpx.Client under the hood, and rewriting every provider
    as truly async would roughly double the codebase for a library at
    this stage. What this gives you is what actually matters for a web
    handler: the event loop isn't blocked while the request is in
    flight. Accepts the same arguments as Gateway.

    Example:
        gateway = AsyncGateway(provider="paystack", api_key="sk_test_...")
        transaction = await gateway.initialize_payment(1000, "a@example.com")
    """

    def __init__(self, *args: Any, **kwargs: Any):
        self._gateway = Gateway(*args, **kwargs)

    @property
    def config(self) -> Config:
        return self._gateway.config

    async def initialize_payment(
        self, amount: int, email: str, currency: str = "NGN", **kwargs: Any
    ) -> Dict[str, Any]:
        return await _run_sync(
            self._gateway.payments.initialize,
            amount=amount,
            email=email,
            currency=currency,
            **kwargs,
        )

    async def verify_payment(self, reference: str) -> Dict[str, Any]:
        return await _run_sync(self._gateway.payments.verify, reference)

    async def charge_authorization(
        self,
        authorization_code: str,
        email: str,
        amount: int,
        currency: str = "NGN",
        idempotency_key: Optional[str] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        return await _run_sync(
            self._gateway.payments.charge_authorization,
            authorization_code=authorization_code,
            email=email,
            amount=amount,
            currency=currency,
            idempotency_key=idempotency_key,
            **kwargs,
        )

    async def create_customer(
        self,
        email: str,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        phone: Optional[str] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        return await _run_sync(
            self._gateway.customers.create,
            email=email,
            first_name=first_name,
            last_name=last_name,
            phone=phone,
            **kwargs,
        )

    async def get_customer(self, customer_code: str) -> Dict[str, Any]:
        return await _run_sync(self._gateway.customers.get, customer_code)

    async def update_customer(
        self, customer_code: str, **kwargs: Any
    ) -> Dict[str, Any]:
        return await _run_sync(self._gateway.customers.update, customer_code, **kwargs)

    async def list_tokens(self, customer_code: str) -> List[Dict[str, Any]]:
        return await _run_sync(self._gateway.tokens.list_for_customer, customer_code)

    async def deactivate_token(self, authorization_code: str) -> Dict[str, Any]:
        return await _run_sync(self._gateway.tokens.deactivate, authorization_code)

    async def verify_webhook(self, payload: bytes, signature: str) -> bool:
        return await _run_sync(self._gateway.verify_webhook, payload, signature)
