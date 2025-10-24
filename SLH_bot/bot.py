import os
import logging
from typing import List
from pydantic import BaseModel
from dotenv import load_dotenv
import httpx

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

load_dotenv()

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
API_BASE = os.getenv("SLH_API_BASE", "").rstrip("/")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(level=LOG_LEVEL)
log = logging.getLogger("slh-bot")

if not TOKEN:
    raise RuntimeError("TELEGRAM_BOT_TOKEN missing")
if not API_BASE:
    raise RuntimeError("SLH_API_BASE missing")

def human(msg: str) -> str:
    return msg.replace("`","'")

async def _get(path: str, params=None):
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{API_BASE}{path}", params=params)
        r.raise_for_status()
        return r.json()

async def _post(path: str, json=None):
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{API_BASE}{path}", json=json)
        r.raise_for_status()
        return r.json()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "SLH Bot is up!\n"
        "/tokeninfo – contract stats\n"
        "/balance <address>\n"
        "/estimate <mint|transfer> <to> <amount>\n"
        "/mint <to> <amount> (owner)\n"
        "/send <to> <amount> (owner)"
    )

async def tokeninfo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        data = await _get("/tokeninfo")
        msg = (
            f"Address: `{data['address']}`\n"
            f"Name: {data['name']}\n"
            f"Symbol: {data['symbol']}\n"
            f"Decimals: {data['decimals']}\n"
            f"TotalSupply: {data['totalSupply']}"
        )
        await update.message.reply_text(msg, parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(f"❌ {e}")

async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) != 1:
        return await update.message.reply_text("Usage: /balance <address>")
    addr = context.args[0]
    try:
        data = await _get(f"/balance/{addr}")
        await update.message.reply_text(f"{data['address']} => {data['balance']}")
    except Exception as e:
        await update.message.reply_text(f"❌ {e}")

async def estimate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) != 3:
        return await update.message.reply_text("Usage: /estimate <mint|transfer> <to> <amount>")
    op, to, amount = context.args
    try:
        data = await _get(f"/estimate/{op}", params={"to": to, "amount": amount})
        gwei = int(data["gasPriceWei"]) / 1_000_000_000
        fee = int(data["totalWei"]) / 1e18
        await update.message.reply_text(
            f"Gas: {data['gas']} | GasPrice: {gwei} gwei | Total: {fee} BNB"
        )
    except Exception as e:
        await update.message.reply_text(f"❌ {e}")

async def mint(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) != 2:
        return await update.message.reply_text("Usage: /mint <to> <amount>")
    to, amount = context.args
    try:
        data = await _post("/mint", json={"to": to, "amount": amount})
        await update.message.reply_text(f"✅ Mint tx: `{data['txHash']}`", parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(f"❌ {e}")

async def send(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) != 2:
        return await update.message.reply_text("Usage: /send <to> <amount>")
    to, amount = context.args
    try:
        data = await _post("/transfer", json={"to": to, "amount": amount})
        await update.message.reply_text(f"✅ Transfer tx: `{data['txHash']}`", parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(f"❌ {e}")

def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("tokeninfo", tokeninfo))
    app.add_handler(CommandHandler("balance", balance))
    app.add_handler(CommandHandler("estimate", estimate))
    app.add_handler(CommandHandler("mint", mint))
    app.add_handler(CommandHandler("send", send))
    app.run_polling()

if __name__ == "__main__":
    main()
