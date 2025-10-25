import os, logging, httpx
from typing import List
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

def _parse_level(val):
    import logging as _L
    if val is None: return _L.INFO
    try: return int(val)
    except: return getattr(_L, str(val).upper(), _L.INFO)

logging.basicConfig(level=_parse_level(os.getenv("LOG_LEVEL","INFO")))
log = logging.getLogger("slh.bot")

API_BASE = os.getenv("SLH_API_BASE","").rstrip("/")
ADMIN_CHAT_IDS = set([s.strip() for s in os.getenv("ADMIN_CHAT_IDS","").split(",") if s.strip()])
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN","")

if not TOKEN:
    raise RuntimeError("Missing TELEGRAM_BOT_TOKEN")

def _api_variants(path:str) -> List[str]:
    base = API_BASE or ""
    return [f"{base}{path}", f"{base}/api{path}", f"{base}/v1{path}"]

async def _get_json(paths: List[str]):
    async with httpx.AsyncClient(timeout=20) as client:
        for url in paths:
            r = await client.get(url)
            if r.status_code == 200:
                return r.json()
        raise RuntimeError(f"GET failed for {paths}")

async def _post_json(paths: List[str], payload: dict):
    async with httpx.AsyncClient(timeout=30) as client:
        for url in paths:
            r = await client.post(url, json=payload)
            if r.status_code == 200:
                return r.json()
        raise RuntimeError(f"POST failed for {paths}")

def _is_admin(chat_id: int) -> bool:
    if not ADMIN_CHAT_IDS: return True
    return str(chat_id) in ADMIN_CHAT_IDS

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "SLH Bot is up!\n"
        "/tokeninfo – contract stats\n"
        "/balance <address>\n"
        "/estimate <mint|transfer> <to> <amount>\n"
        "/mint <to> <amount> (owner)\n"
        "/send <to> <amount> (owner)\n"
    )

async def tokeninfo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        data = await _get_json(_api_variants("/tokeninfo"))
        await update.message.reply_text(
            f"Contract: {data.get('contract')}\n"
            f"Symbol: {data.get('symbol')}\n"
            f"Decimals: {data.get('decimals')}\n"
            f"TotalSupply: {data.get('totalSupply')}\n"
            f"ChainId: {data.get('chainId')}"
        )
    except Exception as e:
        await update.message.reply_text(f"❌ tokeninfo failed: {e}")

async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /balance <address>")
        return
    addr = context.args[0]
    try:
        data = await _get_json(_api_variants(f"/balance/{addr}"))
        await update.message.reply_text(
            f"{data.get('address')}\nBalance: {data.get('balance')} (raw)\nSymbol: {data.get('symbol')}"
        )
    except Exception as e:
        await update.message.reply_text(f"❌ balance failed: {e}")

async def estimate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 3:
        await update.message.reply_text("Usage: /estimate <mint|transfer> <to> <amount>")
        return
    op, to, amount = context.args[0], context.args[1], context.args[2]
    try:
        data = await _get_json(_api_variants(f"/estimate/{op}/{to}/{amount}"))
        await update.message.reply_text(
            f"op={data.get('op')} to={data.get('to')}\namount={data.get('amount')}\n"
            f"gasLimit={data.get('gasLimit')} gasPrice={data.get('gasPrice')}"
        )
    except Exception as e:
        await update.message.reply_text(f"❌ estimate failed: {e}")

async def mint(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Not allowed")
        return
    if len(context.args) < 2:
        await update.message.reply_text("Usage: /mint <to> <amount>")
        return
    to, amount = context.args[0], int(context.args[1])
    try:
        data = await _post_json(_api_variants("/mint"), {"to": to, "amount": amount})
        await update.message.reply_text(f"✅ submitted: {data.get('hash')}")
    except Exception as e:
        await update.message.reply_text(f"❌ mint failed: {e}")

async def send(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Not allowed")
        return
    if len(context.args) < 2:
        await update.message.reply_text("Usage: /send <to> <amount>")
        return
    to, amount = context.args[0], int(context.args[1])
    try:
        data = await _post_json(_api_variants("/transfer"), {"to": to, "amount": amount})
        await update.message.reply_text(f"✅ submitted: {data.get('hash')}")
    except Exception as e:
        await update.message.reply_text(f"❌ send failed: {e}")

def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("tokeninfo", tokeninfo))
    app.add_handler(CommandHandler("balance", balance))
    app.add_handler(CommandHandler("estimate", estimate))
    app.add_handler(CommandHandler("mint", mint))
    app.add_handler(CommandHandler("send", send))
    log.info("Starting bot (run_polling)...")
    app.run_polling(drop_pending_updates=True, allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
