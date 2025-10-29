import os, httpx, asyncio
from typing import Optional

API_BASE = os.getenv("SLH_API_BASE", "").rstrip("/")
INTERNAL_API_KEY = os.getenv("INTERNAL_API_KEY", "").strip()

TIMEOUT = httpx.Timeout(10.0, read=20.0)
_client: Optional[httpx.AsyncClient] = None

async def client() -> httpx.AsyncClient:
    global _client
    if _client is None:
        headers = {}
        if INTERNAL_API_KEY:
            headers["X-Internal-Key"] = INTERNAL_API_KEY
        _client = httpx.AsyncClient(base_url=API_BASE, timeout=TIMEOUT, headers=headers)
    return _client

async def healthz():
    c = await client()
    r = await c.get("/healthz")
    r.raise_for_status()
    return r.json()

async def token_balance(address: str):
    c = await client()
    r = await c.get(f"/token/balance/{address}")
    r.raise_for_status()
    return r.json()

async def transfer_slh(to_addr: str, amount_slh: str):
    c = await client()
    r = await c.post("/transfer/slh", json={"to_addr": to_addr, "amount_slh": amount_slh})
    r.raise_for_status()
    return r.json()

async def aclose():
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None
