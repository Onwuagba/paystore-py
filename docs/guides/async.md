# Async Usage

`AsyncGateway` wraps `Gateway` for FastAPI, async Django views, or any
`asyncio`-based app.

## Why it exists

paystore's providers use a synchronous `httpx.Client` under the hood.
Rewriting every provider as truly async (a second `httpx.AsyncClient`-
based implementation of each) would roughly double the codebase for a
library at this stage, for a benefit most callers don't actually need:
a non-blocking *event loop*, not a non-blocking *socket*.

`AsyncGateway` gives you exactly that — it runs each call in a thread
pool executor (`asyncio.get_running_loop().run_in_executor`), so your
event loop stays free to handle other requests while a payment API
call is in flight. It is **not** a native async HTTP implementation;
if you need that specifically, use `Gateway` directly from inside
`asyncio.to_thread`/an executor yourself, which is functionally
equivalent to what `AsyncGateway` already does for you.

## Usage

```python
from paystore import AsyncGateway

gateway = AsyncGateway(provider="paystack", api_key="sk_test_...")

@app.post("/pay")
async def pay(email: str, amount: int):
    transaction = await gateway.initialize_payment(amount, email)
    return {"url": transaction["authorization_url"]}

@app.post("/webhooks/paystack")
async def webhook(request: Request):
    body = await request.body()
    signature = request.headers.get("X-Paystack-Signature", "")
    await gateway.verify_webhook(body, signature)  # raises PaymentError if invalid
    ...
```

## Method mapping

`AsyncGateway` mirrors `Gateway`'s methods directly rather than the
`.payments`/`.customers`/`.tokens`/`.subscriptions` facade objects:

| `Gateway` | `AsyncGateway` |
|---|---|
| `gateway.payments.initialize(...)` | `await gateway.initialize_payment(...)` |
| `gateway.payments.verify(...)` | `await gateway.verify_payment(...)` |
| `gateway.payments.charge_authorization(...)` | `await gateway.charge_authorization(...)` |
| `gateway.payments.refund(...)` | `await gateway.refund_payment(...)` |
| `gateway.customers.create(...)` | `await gateway.create_customer(...)` |
| `gateway.customers.get(...)` | `await gateway.get_customer(...)` |
| `gateway.customers.update(...)` | `await gateway.update_customer(...)` |
| `gateway.tokens.list_for_customer(...)` | `await gateway.list_tokens(...)` |
| `gateway.tokens.deactivate(...)` | `await gateway.deactivate_token(...)` |
| `gateway.subscriptions.create_plan(...)` | `await gateway.create_plan(...)` |
| `gateway.subscriptions.subscribe(...)` | `await gateway.subscribe(...)` |
| `gateway.subscriptions.cancel(...)` | `await gateway.cancel_subscription(...)` |
| `gateway.verify_webhook(...)` | `await gateway.verify_webhook(...)` |
| `gateway.supports(...)` | `gateway.supports(...)` (plain sync call — it's just a dict lookup, no need to hop threads) |
| `gateway.config` | `gateway.config` (property, same on both) |

All the underlying `Gateway` arguments (`idempotency_key`, `storage`,
provider-specific kwargs, etc.) work the same way through `AsyncGateway`.
