import json
import logging
from typing import Optional

import aiohttp
from fastapi import APIRouter, HTTPException, Request
from telegram import Update
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
)

from .config import settings

logger = logging.getLogger("slh.bot")

router = APIRouter(tags=["telegram"])

_application: Optional[Application] = None


async def _build_application() -> Application:
    if not settings.telegram_bot_token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is not configured")

    app = (
        ApplicationBuilder()
        .token(settings.telegram_bot_token)
        .concurrent_updates(True)
        .build()
    )

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("wallet", cmd_wallet))
    app.add_handler(CommandHandler("set_wallet", cmd_set_wallet))
    app.add_handler(CommandHandler("balances", cmd_balances))

    return app


async def get_application() -> Application:
    global _application
    if _application is None:
        _application = await _build_application()
        await _application.initialize()
        logger.info("Telegram Application initialized.")
    return _application


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
        "📲 רישום / עדכון ארנק SLH\n\n"
        "שלח לי את כתובת ה-BNB ואת כתובת ה-SLH שלך בפורמט הבא:\n"
        "/set_wallet <כתובת_BNB> <כתובת_SLP/SLH_ב-BNB>\n\n"
        "לדוגמה:\n"
        "/set_wallet 0x1234...abcd 0xACb0A0..."
    )
    await update.effective_chat.send_message(text)


async def cmd_set_wallet(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not user:
        return

    if len(context.args) != 2:
        await update.effective_chat.send_message(
            "שימוש: /set_wallet <כתובת_BNB> <כתובת_SLP/SLH_ב-BNB>"
        )
        return

    bnb_address, slh_address = context.args
    base = settings.base_url or "http://127.0.0.1:8000"
    api_url = f"{base}/api/wallet/set"

    payload = {
        "bnb_address": bnb_address,
        "slh_address": slh_address,
    }

    params = {
        "telegram_id": str(user.id),
        "username": user.username or "",
        "first_name": user.first_name or "",
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(api_url, params=params, json=payload) as resp:
                if resp.status != 200:
                    logger.error("set_wallet API error %s", resp.status)
                    await update.effective_chat.send_message(
                        "❌ לא הצלחתי לעדכן את הארנק. נסה שוב מאוחר יותר."
                    )
                    return

    except Exception as e:  # noqa: BLE001
        logger.error("Error calling set_wallet API: %s", e)
        await update.effective_chat.send_message(
            "❌ לא הצלחתי לעדכן את הארנק. נסה שוב מאוחר יותר."
        )
        return

    await update.effective_chat.send_message(
        "✅ הארנק שלך עודכן בהצלחה במערכת SLH."
    )


async def cmd_balances(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not user:
        return

    base = settings.base_url or "http://127.0.0.1:8000"
    api_url = f"{base}/api/wallet/{user.id}/balances"

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(api_url) as resp:
                if resp.status == 404:
                    await update.effective_chat.send_message(
                        "לא נמצא ארנק עבורך. השתמש ב-/wallet ו-/set_wallet קודם."
                    )
                    return
                if resp.status != 200:
                    logger.error("balances API error %s", resp.status)
                    await update.effective_chat.send_message(
                        "❌ בעיית תקשורת עם השרת. נסה שוב מאוחר יותר."
                    )
                    return

                data = await resp.json()

    except Exception as e:  # noqa: BLE001
        logger.error("Error calling balances API: %s", e)
        await update.effective_chat.send_message(
            "❌ בעיית תקשורת עם השרת. נסה שוב מאוחר יותר."
        )
        return

    text = (
        "🏦 *יתרות הארנק שלך (Demo)*\n\n"
        f"📍 כתובת BNB: `{data.get('bnb_address') or '-'}'\n"
        f"📍 כתובת SLH: `{data.get('slh_address') or '-'}'\n\n"
        f"💎 BNB: `{data.get('bnb_balance', 0):.6f}`\n"
        f"🪙 SLH: `{data.get('slh_balance', 0):.2f}`\n\n"
        "_(כרגע היתרות נשלפות מדמו – בהמשך נחבר ל-BscScan/TON)_"
    )

    await update.effective_chat.send_message(text, parse_mode="Markdown")


@router.post("/telegram/webhook")
async def telegram_webhook(request: Request) -> dict:
    try:
        body = await request.body()
        if not body:
            raise HTTPException(status_code=400, detail="Empty body")

        data = json.loads(body.decode("utf-8"))
        app = await get_application()
        update = Update.de_json(data, app.bot)
        await app.process_update(update)

        return {"ok": True}
    except json.JSONDecodeError:
        logger.error("Invalid JSON in webhook")
        raise HTTPException(status_code=400, detail="Invalid JSON")
    except Exception as e:  # noqa: BLE001
        logger.error("Error processing webhook: %s", e)
        raise HTTPException(status_code=500, detail="Internal server error")