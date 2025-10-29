import os, re, logging, asyncio
from decimal import Decimal, InvalidOperation
from pythonjsonlogger import jsonlogger
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    Application, CommandHandler, MessageHandler, ConversationHandler,
    ContextTypes, filters
)
from keyboards import main_menu
from user_store import UserStore
import slh_api_client as api

load_dotenv()

# Logging JSON
handler = logging.StreamHandler()
formatter = jsonlogger.JsonFormatter("%(asctime)s %(levelname)s %(name)s %(message)s")
handler.setFormatter(formatter)
root = logging.getLogger()
root.handlers = [handler]
root.setLevel(getattr(logging, os.getenv("LOG_LEVEL","INFO").upper(), logging.INFO))
log = logging.getLogger("slh.bot")

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN","").strip()
SLH_API_BASE = os.getenv("SLH_API_BASE","").strip()
SHOW_ALWAYS_MENU = os.getenv("SHOW_ALWAYS_MENU","true").lower() == "true"
APPROVED_CHAT_ID = int(os.getenv("APPROVED_CHAT_ID","0") or 0)

if not TOKEN:
    raise RuntimeError("TELEGRAM_BOT_TOKEN is required")

ADDR_RE = re.compile(r"^0x[a-fA-F0-9]{40}$")
store = UserStore(os.getenv("PERSIST_FILE","data/users.json"))

async def is_allowed(update: Update) -> bool:
    if APPROVED_CHAT_ID == 0:
        return True
    chat_id = update.effective_chat.id if update.effective_chat else 0
    return chat_id == APPROVED_CHAT_ID

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_allowed(update):
        await update.effective_message.reply_text("Not authorized.")
        return
    text = [
        "Welcome to SLH Wallet Bot 🪙",
        f"API: {SLH_API_BASE or 'not set'}",
        "Use /setwallet to save your wallet, /balance to check token balance, /send <amount> <to> to transfer."
    ]
    await update.effective_message.reply_text("\n".join(text), reply_markup=main_menu() if SHOW_ALWAYS_MENU else None)

async def setwallet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_allowed(update):
        await update.effective_message.reply_text("Not authorized.")
        return
    args = context.args
    if not args:
        await update.effective_message.reply_text("Usage: /setwallet <0xAddress>")
        return
    addr = args[0].strip()
    if not ADDR_RE.match(addr):
        await update.effective_message.reply_text("Invalid address format.")
        return
    await store.set_wallet(update.effective_user.id, addr)
    await update.effective_message.reply_text(f"Saved wallet: {addr}")

async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_allowed(update):
        await update.effective_message.reply_text("Not authorized.")
        return
    addr = await store.get_wallet(update.effective_user.id)
    if not addr:
        await update.effective_message.reply_text("No wallet set. Use /setwallet <0xAddress>")
        return
    try:
        res = await api.token_balance(addr)
        await update.effective_message.reply_text(f"Balance: {res.get('balance')} (decimals={res.get('decimals')})")
    except Exception as e:
        log.exception("balance error")
        await update.effective_message.reply_text(f"Error: {e}")

async def send_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_allowed(update):
        await update.effective_message.reply_text("Not authorized.")
        return
    args = context.args
    if len(args) < 2:
        await update.effective_message.reply_text("Usage: /send <amount> <toAddress>")
        return
    amount_str, to_addr = args[0], args[1]
    try:
        amount = Decimal(amount_str)
        if amount <= 0:
            raise InvalidOperation()
    except Exception:
        await update.effective_message.reply_text("Invalid amount.")
        return
    if not ADDR_RE.match(to_addr):
        await update.effective_message.reply_text("Invalid address.")
        return
    try:
        res = await api.transfer_slh(to_addr, str(amount))
        await update.effective_message.reply_text(f"Sent. tx: {res.get('tx_hash')}")
    except Exception as e:
        log.exception("send error")
        await update.effective_message.reply_text(f"Error: {e}")

async def text_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_allowed(update):
        return
    txt = (update.effective_message.text or "").strip().lower()
    if txt.startswith("set wallet") or "set wallet" in txt or "setwallet" in txt:
        await update.effective_message.reply_text("Use: /setwallet <0xAddress>")
    elif "balance" in txt:
        await balance(update, context)
    elif "send" in txt:
        await update.effective_message.reply_text("Use: /send <amount> <toAddress>")
    else:
        await start(update, context)

async def on_shutdown(app):
    await api.aclose()

def main():
    application = Application.builder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("setwallet", setwallet))
    application.add_handler(CommandHandler("balance", balance))
    application.add_handler(CommandHandler("send", send_cmd))
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), text_router))
    application.run_polling()

if __name__ == "__main__":
    main()
