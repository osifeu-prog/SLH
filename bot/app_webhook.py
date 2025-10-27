import re, logging, asyncio
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from keyboards import main_menu
from settings import TELEGRAM_BOT_TOKEN, PERSIST_FILE
from user_store import UserStore
from slh_api_client import transfer_slh, healthz

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("SLHBot")

WALLET_RE = re.compile(r"^0x[a-fA-F0-9]{40}$")

store = UserStore(PERSIST_FILE)

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await update.message.reply_text(
        f"שלום {user.first_name} 👋\nברוך הבא לבוט SLH. בחר פעולה:",
        reply_markup=main_menu()
    )

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (update.message.text or "").strip()

    # Route by button
    if text == "ℹ️ עזרה":
        await update.message.reply_text(
            "שלח/י 0x… כדי לשמור כתובת MetaMask\nבחר/י '💸 העברה' כדי לבצע שליחה", reply_markup=main_menu())
        return

    if text == "💳 הזנת MetaMask":
        await update.message.reply_text("💳 שלח/י כאן את כתובת ה-MetaMask (0x...)",
                                        reply_markup=main_menu())
        context.user_data["mode"] = "await_wallet"
        return

    if text == "📊 יתרה":
        w = store.get_wallet(update.effective_user.id)
        h = await healthz()
        net = h.get("network_mode", "unknown")
        chain = h.get("chain_id", "?")
        await update.message.reply_text(
            f"🌐 רשת: {net.upper()}\n👛 ארנק: {w or '—'}\n\n• SLH token: {h.get('token')}\n(chain_id={chain})",
            reply_markup=main_menu())
        return

    if text == "💸 העברה":
        w = store.get_wallet(update.effective_user.id)
        if not w:
            await update.message.reply_text("לא נמצא ארנק שמור. שלח/י כעת כתובת MetaMask (0x...).",
                                            reply_markup=main_menu())
            context.user_data["mode"] = "await_wallet"
            return
        await update.message.reply_text("🎁 שליחת SLH: כתוב/כתבי עכשיו את כתובת היעד (0x...).",
                                        reply_markup=main_menu())
        context.user_data["mode"] = "await_to"
        return

    # Conversation logic
    mode = context.user_data.get("mode")

    if mode == "await_wallet":
        if WALLET_RE.match(text):
            store.set_wallet(update.effective_user.id, text)
            await update.message.reply_text("✅ נשמרה כתובת MetaMask.\nאפשר ללחוץ '📊 יתרה' או '💸 העברה'.",
                                            reply_markup=main_menu())
            context.user_data["mode"] = None
        else:
            await update.message.reply_text("❌ כתובת לא תקפה. נסו שוב (0x… 42 תווים).",
                                            reply_markup=main_menu())
        return

    if mode == "await_to":
        if WALLET_RE.match(text):
            context.user_data["to_addr"] = text
            context.user_data["mode"] = "await_amount"
            await update.message.reply_text("מצוין. כעת שלח/י סכום (למשל 0.1).",
                                            reply_markup=main_menu())
        else:
            await update.message.reply_text("❌ כתובת לא תקפה. הזינו 0x…", reply_markup=main_menu())
        return

    if mode == "await_amount":
        amt = text.replace(",", ".")
        try:
            float(amt)
        except:
            await update.message.reply_text("❌ סכום לא תקין. נסו שוב (למשל 0.1).", reply_markup=main_menu())
            return

        to_addr = context.user_data.get("to_addr")
        await update.message.reply_text("⏳ מעביר SLH…", reply_markup=main_menu())

        res = await transfer_slh(to_addr, amt)
        if res.get("ok"):
            await update.message.reply_text(f"✅ הועבר! tx_hash:\n{res.get('tx_hash')}",
                                            reply_markup=main_menu())
        else:
            await update.message.reply_text(f"❗️ ההעברה נכשלה: {res}",
                                            reply_markup=main_menu())
        context.user_data["mode"] = None
        return

    # Fallback: if user sends 0x… without pressing button, save as wallet
    if WALLET_RE.match(text):
        store.set_wallet(update.effective_user.id, text)
        await update.message.reply_text("✅ נשמרה כתובת MetaMask.\nאפשר ללחוץ '📊 יתרה' או '💸 העברה'.",
                                        reply_markup=main_menu())
        return

    await update.message.reply_text("לא זוהה. השתמש בתפריט למטה או /start",
                                    reply_markup=main_menu())

async def main():
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    await app.start()
    await app.updater.start_polling()
    await app.updater.idle()

if __name__ == "__main__":
    asyncio.run(main())
