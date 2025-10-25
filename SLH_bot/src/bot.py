import os, asyncio, logging, httpx
from typing import Optional
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

logging.basicConfig(level=os.getenv("LOG_LEVEL","INFO"))
log = logging.getLogger("slh.bot")

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN","").strip()
API_BASE = os.environ.get("SLH_API_BASE","https://slhapi-bot.up.railway.app").rstrip("/")
ADMIN_IDS = [i for i in os.environ.get("ADMIN_CHAT_IDS","").split(",") if i]

def fmt(e: Exception)->str:
    return f"❌ {type(e).__name__}: {e}"

async def _api_get(path: str):
    url = f"{API_BASE}{path}"
    async with httpx.AsyncClient(timeout=20) as cx:
        r = await cx.get(url); r.raise_for_status(); return r.json()

async def _api_post(path: str, params: dict):
    url = f"{API_BASE}{path}"
    async with httpx.AsyncClient(timeout=40) as cx:
        r = await cx.post(url, params=params); r.raise_for_status(); return r.json()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "SLH Bot is up!\n/tokeninfo – contract stats\n/balance <address>\n/estimate <mint|transfer> <to> <amount>\n/mint <to> <amount> (owner)\n/send <to> <amount> (owner)"
    )

async def tokeninfo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        data = await _api_get("/tokeninfo")
        if not data or "address" not in data:
            data = await _api_get("/api/tokeninfo")
        await update.message.reply_text(
            f"Token: {data.get('symbol')} ({data.get('name')})\n"
            f"Address: {data.get('address')}\n"
            f"Decimals: {data.get('decimals')}\n"
            f"Total Supply: {data.get('totalSupply')}\n"
            f"ChainId: {data.get('chainId')}"
        )
    except Exception as e:
        await update.message.reply_text(fmt(e))

async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) != 1:
        return await update.message.reply_text("Usage: /balance <address>")
    addr = context.args[0]
    try:
        data = await _api_get(f"/balance/{addr}")
        await update.message.reply_text(f"Address: {data.get('address')}\nBalance: {data.get('balance')}")
    except Exception as e:
        await update.message.reply_text(fmt(e))

async def estimate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) != 3:
        return await update.message.reply_text("Usage: /estimate <mint|transfer> <to> <amount>")
    op, to, amount = context.args
    try:
        data = await _api_get(f\"/estimate/{op}/{to}/{amount}\")
        await update.message.reply_text(f\"Op: {op}\nGas: {data.get('gas')}\nGasPrice: {data.get('gasPrice')}\")
    except Exception as e:
        await update.message.reply_text(fmt(e))

def _is_admin(uid: Optional[int])->bool:
    return uid is not None and str(uid) in ADMIN_IDS if ADMIN_IDS else True

async def mint(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) != 2:
        return await update.message.reply_text("Usage: /mint <to> <amount>")
    if not _is_admin(update.effective_user.id):
        return await update.message.reply_text("Not allowed.")
    to, amount = context.args
    try:
        data = await _api_post("/mint", {"to": to, "amount": int(amount)})
        await update.message.reply_text(f"Mint tx: {data.get('txHash')}\nStatus: {data.get('status')}")
    except Exception as e:
        await update.message.reply_text(fmt(e))

async def send(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) != 2:
        return await update.message.reply_text("Usage: /send <to> <amount>")
    if not _is_admin(update.effective_user.id):
        return await update.message.reply_text("Not allowed.")
    to, amount = context.args
    try:
        data = await _api_post("/transfer", {"to": to, "amount": int(amount)})
        await update.message.reply_text(f"Transfer tx: {data.get('txHash')}\nStatus: {data.get('status')}")
    except Exception as e:
        await update.message.reply_text(fmt(e))

async def main():
    if not TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is missing")
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("tokeninfo", tokeninfo))
    app.add_handler(CommandHandler("balance", balance))
    app.add_handler(CommandHandler("estimate", estimate))
    app.add_handler(CommandHandler("mint", mint))
    app.add_handler(CommandHandler("send", send))
    log.info("Starting bot (run_polling)...")
    await app.run_polling(close_loop=False, allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    asyncio.run(main())
