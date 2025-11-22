from __future__ import annotations

import logging
from typing import Final

import httpx
from telegram import Update
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
)

from .config import TELEGRAM_BOT_TOKEN, API_BASE_URL

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("slh_wallet.bot")

API_TIMEOUT: Final = 10.0


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not user:
        return

    text = (
        f"שלום @{user.username or user.id}! 🌐\n\n"
        "ברוך הבא ל-SLH Community Wallet 🚀\n\n"
        "פקודות זמינות:\n"
        "/wallet - רישום/עדכון הארנק שלך\n"
        "/balances - צפייה ביתרות (SLH פנימי + BNB/SLH ברשת)\n\n"
        "המערכת אינה דורשת סיסמא – רק טלגרם + כתובות ארנק."
    )
    await update.effective_chat.send_message(text)


async def cmd_wallet(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not user:
        return

    text = (
        "📲 *רישום / עדכון ארנק SLH*\n\n"
        "שלח לי את כתובת ה-BNB ואת כתובת ה-SLH שלך בפורמט הבא:\n"
        "`/set_wallet <כתובת_BNB> <כתובת_SLP/SLH_ב-BNB>`\n\n"
        "לדוגמה:\n"
        "`/set_wallet 0x1234...abcd 0xACb0A0...`"
    )
    await update.effective_chat.send_message(text, parse_mode="Markdown")


async def cmd_set_wallet(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not user:
        return

    if len(context.args) < 1:
        await update.effective_chat.send_message("שימוש: /set_wallet <כתובת_BNB> [כתובת_SLH (אופציונלי)]")
        return

    bnb_address = context.args[0].strip()
    slh_address = context.args[1].strip() if len(context.args) > 1 else bnb_address

    payload = {
        "telegram_id": str(user.id),
        "username": user.username,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "bnb_address": bnb_address,
        "slh_address": slh_address,
    }

    try:
        async with httpx.AsyncClient(timeout=API_TIMEOUT) as client:
            resp = await client.post(f"{API_BASE_URL}/api/wallet/register", json=payload)
            if resp.status_code != 200:
                logger.error("Register wallet failed: %s %s", resp.status_code, resp.text)
                await update.effective_chat.send_message("❌ לא הצלחתי לעדכן את הארנק. נסה שוב מאוחר יותר.")
                return
    except Exception as e:  # noqa: BLE001
        logger.error("Error talking to API: %s", e)
        await update.effective_chat.send_message("❌ בעיית תקשורת עם השרת. נסה שוב מאוחר יותר.")
        return

    await update.effective_chat.send_message("✅ הארנק שלך נרשם/עודכן בהצלחה במערכת SLH.")


async def cmd_balances(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not user:
        return

    try:
        async with httpx.AsyncClient(timeout=API_TIMEOUT) as client:
            resp = await client.get(f"{API_BASE_URL}/api/wallet/{user.id}/balances")
            if resp.status_code == 404:
                await update.effective_chat.send_message(
                    "לא נמצא ארנק. השתמש ב-/wallet ולאחר מכן ב-/set_wallet כדי לרשום ארנק."
                )
                return
            resp.raise_for_status()
            data = resp.json()
    except Exception as e:  # noqa: BLE001
        logger.error("Error fetching balances: %s", e)
        await update.effective_chat.send_message("❌ בעיית תקשורת עם השרת. נסה שוב מאוחר יותר.")
        return

    text = (
        "🏦 *יתרות SLH ו-BNB (תצוגה בסיסית)*\n\n"
        f"💎 BNB (on-chain): `{data.get('bnb_balance', 0):.6f}`\n"
        f"🪙 SLH on-chain: `{data.get('slh_balance_chain', 0):.6f}`\n"
        f"🧾 SLH פנימי: `{data.get('slh_balance_internal', 0):.6f}`\n\n"
        f"📍 BNB: `{data.get('bnb_address')}`\n"
        f"📍 SLH: `{data.get('slh_address')}`"
    )
    await update.effective_chat.send_message(text, parse_mode="Markdown")


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await cmd_start(update, context)


def main() -> None:
    app: Application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("wallet", cmd_wallet))
    app.add_handler(CommandHandler("set_wallet", cmd_set_wallet))
    app.add_handler(CommandHandler("balances", cmd_balances))

    logger.info("Starting SLH Wallet bot (polling)...")
    app.run_polling()


if __name__ == "__main__":
    main()
