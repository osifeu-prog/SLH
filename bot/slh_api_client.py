import httpx, os

SLH_API_BASE = os.getenv("SLH_API_BASE", "https://slhapi-bot.up.railway.app")

async def transfer_slh(to_addr:str, amount_slh:str) -> dict:
    url = f"{SLH_API_BASE}/transfer/slh"
    payload = {"to_addr": to_addr, "amount_slh": amount_slh}
    timeout = httpx.Timeout(20.0, connect=20.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        r = await client.post(url, json=payload)
        try:
            data = r.json()
        except Exception:
            data = {"ok": False, "error": f"http {r.status_code}: {r.text}"}
        return data

async def healthz() -> dict:
    url = f"{SLH_API_BASE}/healthz"
    async with httpx.AsyncClient(timeout=10.0) as client:
        r = await client.get(url)
        try:
            return r.json()
        except Exception:
            return {"ok": False, "error": r.text}
