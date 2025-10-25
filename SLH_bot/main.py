import os, time, json, asyncio, httpx
from dotenv import load_dotenv

# Load env file in same dir (Railway יזריק vars משלו)
env_path = os.path.join(os.path.dirname(__file__), "bot.env")
if os.path.exists(env_path):
    load_dotenv(env_path)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
SLH_API_BASE = os.getenv("SLH_API_BASE", "").rstrip("/")
BOT_MODE = (os.getenv("BOT_MODE") or "polling").lower()
ADMIN_IDS = [s.strip() for s in (os.getenv("ADMIN_CHAT_IDS") or "").split(",") if s.strip()]
DEFAULT_WALLET = os.getenv("DEFAULT_WALLET") or ""
SELA_AMOUNT = os.getenv("SELA_AMOUNT") or "3"
LOG_LEVEL = os.getenv("LOG_LEVEL","INFO")

TG = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"

def log(msg): 
    if LOG_LEVEL.upper() in ("INFO","DEBUG"): 
        print(msg, flush=True)

async def api_get(path):
    async with httpx.AsyncClient(timeout=15) as cli:
        r = await cli.get(f"{SLH_API_BASE}{path}")
        r.raise_for_status()
        return r.json()

async def api_post(path, payload):
    async with httpx.AsyncClient(timeout=30) as cli:
        r = await cli.post(f"{SLH_API_BASE}{path}", json=payload)
        r.raise_for_status()
        return r.json()

async def send_text(chat_id, text):
    async with httpx.AsyncClient(timeout=15) as cli:
        await cli.post(f"{TG}/sendMessage", json={"chat_id": chat_id, "text": text})

def is_admin(chat_id:str) -> bool:
    return (str(chat_id) in ADMIN_IDS) if ADMIN_IDS else False

HELP = (
    "SLH Bot is up!\n"
    "/tokeninfo  contract stats\n"
    f"/balance <address>\n"
    f"/estimate <mint|transfer> <to> <amount>\n"
    f"/mint <to> <amount> (owner)\n"
    f"/send <to> <amount> (owner)\n"
)

async def handle_cmd(chat_id, text):
    parts = text.strip().split()
    cmd = parts[0].lower()

    try:
        if cmd in ("/start","/help"):
            await send_text(chat_id, HELP)
        elif cmd == "/tokeninfo":
            data = await api_get("/tokeninfo")
            await send_text(chat_id, json.dumps(data, ensure_ascii=False))
        elif cmd == "/balance":
            if len(parts) < 2:
                await send_text(chat_id, "Usage: /balance <address>")
            else:
                addr = parts[1]
                data = await api_get(f"/balance/{addr}")
                await send_text(chat_id, json.dumps(data))
        elif cmd == "/estimate":
            if len(parts) < 4:
                await send_text(chat_id, "Usage: /estimate <mint|transfer> <to> <amount>")
            else:
                payload = {"kind": parts[1], "to": parts[2], "amount": parts[3]}
                data = await api_post("/estimate", payload)
                await send_text(chat_id, json.dumps(data))
        elif cmd == "/mint":
            if len(parts) < 3:
                await send_text(chat_id, "Usage: /mint <to> <amount>")
            elif not is_admin(chat_id):
                await send_text(chat_id, "Unauthorized")
            else:
                payload = {"to": parts[1], "amount": parts[2]}
                data = await api_post("/mint", payload)
                await send_text(chat_id, json.dumps(data))
        elif cmd == "/send":
            if len(parts) < 3:
                await send_text(chat_id, "Usage: /send <to> <amount>")
            elif not is_admin(chat_id):
                await send_text(chat_id, "Unauthorized")
            else:
                payload = {"to": parts[1], "amount": parts[2]}
                data = await api_post("/send", payload)
                await send_text(chat_id, json.dumps(data))
        else:
            await send_text(chat_id, "Unknown command. /help")
    except httpx.HTTPStatusError as e:
        await send_text(chat_id, f"API error: {e.response.status_code} {e.response.text}")
    except Exception as e:
        await send_text(chat_id, f"Error: {e}")

async def polling_loop():
    offset = None
    while True:
        try:
            async with httpx.AsyncClient(timeout=60) as cli:
                r = await cli.post(f"{TG}/getUpdates", json={"offset": offset, "timeout": 30})
                updates = r.json().get("result", [])
                for upd in updates:
                    offset = upd["update_id"] + 1
                    msg = upd.get("message") or upd.get("edited_message") or {}
                    chat_id = msg.get("chat", {}).get("id")
                    text = msg.get("text","")
                    if chat_id and text:
                        await handle_cmd(chat_id, text)
        except Exception as e:
            log(f"polling err: {e}")
            await asyncio.sleep(2)

async def webhook_mode():
    # רישום וובהוק פשוט (שרת חיצוני יקבל POST ויעביר ללוגים בלבד  מומלץ להישאר Polling בשלב זה)
    public_base = os.getenv("BOT_WEBHOOK_PUBLIC_BASE")
    path = os.getenv("BOT_WEBHOOK_PATH","/tg")
    secret = os.getenv("BOT_WEBHOOK_SECRET","")
    if not public_base:
        log("BOT_WEBHOOK_PUBLIC_BASE not set; falling back to polling")
        return await polling_loop()

    url = f"{public_base.rstrip('/')}{path}"
    async with httpx.AsyncClient(timeout=15) as cli:
        await cli.post(f"{TG}/setWebhook", json={"url": url, "secret_token": secret})
    log(f"Webhook set to {url} (secret_token hidden)")
    # כדי לא לסבך עם שרת HTTP נוסף פה — נשאר ב-idle
    while True:
        await asyncio.sleep(60)

def main():
    if not TELEGRAM_BOT_TOKEN or not SLH_API_BASE:
        print("ENV missing: TELEGRAM_BOT_TOKEN or SLH_API_BASE", flush=True)
        return
    if BOT_MODE == "webhook":
        asyncio.run(webhook_mode())
    else:
        asyncio.run(polling_loop())

if __name__ == "__main__":
    main()
