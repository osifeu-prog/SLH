
import os, json, logging, asyncio
from typing import Optional
import httpx
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

API_BASE = os.getenv("SLH_API_BASE", "").rstrip("/")
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
PUBLIC_URL = os.getenv("PUBLIC_URL", "").rstrip("/")
WEBHOOK_ROUTE = os.getenv("WEBHOOK_ROUTE", "/webhook")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

logging.basicConfig(level=getattr(logging, LOG_LEVEL, logging.INFO))
log = logging.getLogger("slh.bot")

def _api() -> httpx.AsyncClient:
    if not API_BASE:
        raise RuntimeError("SLH_API_BASE missing")
    return httpx.AsyncClient(base_url=API_BASE, timeout=20.0)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "SLH Bot is up.\n"
        "Commands:\n"
        "/tokeninfo\n"
        "/balance <address>\n"
        "/estimate <mint|transfer> <to> <amount_wei>\n"
        "/mint <to> <amount_wei>\n"
        "/send <to> <amount_wei>"
    )

async def tokeninfo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    async with _api() as c:
        r = await c.get("/tokeninfo")
        if r.status_code != 200:
            await update.message.reply_text(f"Error: {r.status_code} {r.text}")
            return
        data = r.json()
        await update.message.reply_text(json.dumps(data, indent=2))

async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /balance <address>")
        return
    addr = context.args[0]
    async with _api() as c:
        r = await c.get(f"/balance/{addr}")
        await update.message.reply_text(r.text)

async def estimate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 3:
        await update.message.reply_text("Usage: /estimate <mint|transfer> <to> <amount_wei>")
        return
    op, to, amount = context.args[0], context.args[1], context.args[2]
    async with _api() as c:
        r = await c.get(f"/estimate/{op}", params={"to": to, "amount": amount})
        await update.message.reply_text(r.text)

async def do_mint(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await update.message.reply_text("Usage: /mint <to> <amount_wei>")
        return
    to, amount = context.args[0], context.args[1]
    async with _api() as c:
        r = await c.post("/mint", json={"to": to, "amount": amount})
        await update.message.reply_text(r.text)

async def do_send(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await update.message.reply_text("Usage: /send <to> <amount_wei>")
        return
    to, amount = context.args[0], context.args[1]
    async with _api() as c:
        r = await c.post("/transfer", json={"to": to, "amount": amount})
        await update.message.reply_text(r.text)

async def main():
    if not TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN missing")
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("tokeninfo", tokeninfo))
    app.add_handler(CommandHandler("balance", balance))
    app.add_handler(CommandHandler("estimate", estimate))
    app.add_handler(CommandHandler("mint", do_mint))
    app.add_handler(CommandHandler("send", do_send))

    if not PUBLIC_URL:
        log.warning("PUBLIC_URL not set; falling back to polling")
        await app.initialize()
        await app.start()
        await app.updater.start_polling()
        log.info("Running polling...")
        await asyncio.Event().wait()
    else:
        route = WEBHOOK_ROUTE if WEBHOOK_ROUTE.startswith("/") else "/" + WEBHOOK_ROUTE
        log.info("Starting webhook at %s%s", PUBLIC_URL, route)
        app.run_webhook(
            listen="0.0.0.0",
            port=int(os.getenv("PORT", "8080")),
            webhook_url=f"{PUBLIC_URL}{route}",
            secret_token=None,
        )

if __name__ == "__main__":
    asyncio.run(main())
