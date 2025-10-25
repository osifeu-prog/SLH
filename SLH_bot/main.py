import os
import asyncio
import json
from typing import Optional
import httpx
from fastapi import FastAPI, Request

BOT_MODE     = os.getenv("BOT_MODE", "polling").lower()   # polling | webhook
TOKEN        = os.getenv("TELEGRAM_BOT_TOKEN", "")
SLH_API_BASE = os.getenv("SLH_API_BASE", "").rstrip("/")
ADMIN_IDS    = [s.strip() for s in (os.getenv("ADMIN_CHAT_IDS","") or "").split(",") if s.strip()]
DEFAULT_WAL  = os.getenv("DEFAULT_WALLET")

# Webhook env
WEBHOOK_BASE = os.getenv("BOT_WEBHOOK_PUBLIC_BASE","").rstrip("/")
WEBHOOK_PATH = os.getenv("BOT_WEBHOOK_PATH","/tg")
WEBHOOK_SECRET = os.getenv("BOT_WEBHOOK_SECRET")

app = FastAPI(title="SLH Bot", version="1.0.0")
client = httpx.AsyncClient(timeout=20)

HELP = (
"/tokeninfo – contract stats\n"
"/balance <address>\n"
"/estimate <mint|transfer> <to> <amount>\n"
"/mint <to> <amount> (owner)\n"
"/send <to> <amount> (owner)"
)

async def tg_send(chat_id: int, text: str):
    if not TOKEN: return
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    await client.post(url, data={"chat_id": chat_id, "text": text})

async def api_get(path: str):
    url = f"{SLH_API_BASE}{path}"
    return await client.get(url)

async def api_post(path: str, payload: dict):
    url = f"{SLH_API_BASE}{path}"
    return await client.post(url, json=payload)

async def handle_cmd(chat_id: int, text: str):
    t = (text or "").strip()
    if t == "/start":
        await tg_send(chat_id, "SLH Bot is up!\n"+HELP); return

    if t.startswith("/tokeninfo"):
        try:
            r = await api_get("/tokeninfo")
            await tg_send(chat_id, r.text if r.status_code==200 else f"❌ tokeninfo failed ({r.status_code})")
        except Exception as e:
            await tg_send(chat_id, f"❌ tokeninfo failed: {e}")
        return

    if t.startswith("/balance"):
        parts = t.split()
        if len(parts) != 2:
            await tg_send(chat_id, "Usage: /balance <address>"); return
        try:
            r = await api_get(f"/balance/{parts[1]}")
            await tg_send(chat_id, r.text if r.status_code==200 else f"❌ balance failed ({r.status_code})")
        except Exception as e:
            await tg_send(chat_id, f"❌ balance failed: {e}")
        return

    if t.startswith("/mint") or t.startswith("/send"):
        parts = t.split()
        if len(parts) != 3:
            await tg_send(chat_id, f"Usage: {parts[0]} <to> <amount>"); return
        cmd, to, amt = parts[0], parts[1], parts[2]
        path = "/mint" if cmd=="/mint" else "/send"
        try:
            r = await api_post(path, {"to": to, "amount": int(amt)})
            await tg_send(chat_id, r.text if r.status_code==200 else f"❌ {cmd[1:]} failed ({r.status_code})")
        except Exception as e:
            await tg_send(chat_id, f"❌ {cmd[1:]} failed: {e}")
        return

    await tg_send(chat_id, "Unknown command.\n"+HELP)

# -------- Polling --------
async def polling_loop():
    if not TOKEN: return
    last_update_id = 0
    base = f"https://api.telegram.org/bot{TOKEN}"
    while True:
        try:
            r = await client.post(f"{base}/getUpdates", data={"timeout": 30, "offset": last_update_id+1})
            j = r.json()
            for upd in j.get("result",[]):
                last_update_id = upd["update_id"]
                msg = upd.get("message") or upd.get("edited_message")
                if not msg: continue
                chat_id = msg["chat"]["id"]
                text = msg.get("text","")
                await handle_cmd(chat_id, text)
        except Exception:
            await asyncio.sleep(2)

# -------- Webhook --------
@app.post(WEBHOOK_PATH)
async def webhook(request: Request):
    if WEBHOOK_SECRET:
        if request.headers.get("X-Telegram-Bot-Api-Secret-Token") != WEBHOOK_SECRET:
            return {"ok":False}
    upd = await request.json()
    msg = upd.get("message") or upd.get("edited_message")
    if msg:
        chat_id = msg["chat"]["id"]; text = msg.get("text","")
        await handle_cmd(chat_id, text)
    return {"ok":True}

# -------- Entrypoint (for polling run) --------
async def _main():
    if BOT_MODE == "polling":
        await polling_loop()

if __name__ == "__main__":
    asyncio.run(_main())
