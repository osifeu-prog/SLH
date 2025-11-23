from __future__ import annotations

import asyncio
import logging
from typing import Optional

from fastapi import APIRouter, Body, HTTPException
from telegram import Update
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
)

from .config import settings
from .db import SessionLocal
from .models import Wallet

logger = logging.getLogger("slh.bot")

router = APIRouter(
    prefix="/telegram",
    tags=["telegram"],
)

_application: Optional[Application] = None
_application_lock = asyncio.Lock()


def _normalize_address(addr: Optional[str]) -> Optional[str]:
    if addr is None:
        return None
    addr = addr.strip()
    return addr or None


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------


def _upsert_wallet_sync(
    telegram_id: str,
    username: Optional[str],
    first_name: Optional[str],
    bnb_address: str,
    ton_address: Optional[str],
) -> Wallet:
    """
    פעולה סינכרונית שרצה בתוך thread לצורך גישה ל-DB.
    """
    session = SessionLocal()
    try:
        wallet = session.get(Wallet, telegram_id)
        if wallet is None:
            wallet = Wallet(
                telegram_id=telegram_id,
                username=username,
                first_name=first_name,
                bnb_address=bnb_address,
                ton_address=ton_address,
            )
            session.add(wallet)
        else:
            wallet.username = username or wallet.username
            wallet.first_name = first_name or wallet.first_name
            wallet.bnb_address = bnb_address
            wallet.ton_address = ton_address

        session.commit()
        session.refresh(wallet)
        return wallet
    finally:
        session.close()


def _get_wallet_sync(telegram_id: str) -> Optional[Wallet]:
    session = SessionLocal()
    try:
        return session.get(Wallet, telegram_id)
    finally:
        session.close()


# ---------------------------------------------------------------------------
# Telegram command handlers
# ---------------------------------------------------------------------------


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if user is None:
        return

    text = (
        f"שלום @{user.username or user.id}! 🌐\n\n"
        "ברוך הבא ל-SLH Community Wallet 🚀\n\n"
        "פקודות זמינות:\n"
        "/wallet - רישום/עדכון הארנק שלך\n"
        "/balances - צפייה ביתרות (כרגע 0, בסיס לממשק עתידי)\n\n"
        "הרעיון: להזין כתובת BNB (שמשמשת גם ל-SLH באותה כתובת), "
        "ובעתיד גם כתובת TON לצורך אימות זהות והרשאות קהילתיות."
    )
    await update.effective_chat.send_message(text)


async def cmd_wallet(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if user is None:
        return

    text = (
        "📲 רישום / עדכון ארנק SLH\n\n"
        "שלח לי את כתובת ה-BNB שלך (אותה כתובת משמשת גם למטבע SLH):\n"
        "/set_wallet <כתובת_BNB>\n\n"
        "אם כבר יש לך גם ארנק TON, אתה יכול להוסיף אותו:\n"
        "/set_wallet <כתובת_BNB> <כתובת_TON>\n\n"
        "דוגמה:\n"
        "/set_wallet 0xd0617b54fb4b6b66307846f217b4d685800e3da4\n"
        "/set_wallet 0xd0617b54fb4b6b66307846f217b4d685800e3da4 UQCXXXXX..."
    )
    await update.effective_chat.send_message(text)


async def cmd_set_wallet(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    chat = update.effective_chat
    if user is None or chat is None:
        return

    args = context.args or []
    if len(args) == 0:
        await chat.send_message(
            "שימוש:\n"
            "/set_wallet <כתובת_BNB>\n"
            "או:\n"
            "/set_wallet <כתובת_BNB> <כתובת_TON>"
        )
        return

    bnb_address = _normalize_address(args[0])
    ton_address = _normalize_address(args[1]) if len(args) > 1 else None

    if not bnb_address:
        await chat.send_message("❌ כתובת BNB לא תקינה.")
        return

    telegram_id = str(user.id)
    username = user.username or None
    first_name = user.first_name or None

    try:
        wallet = await asyncio.to_thread(
            _upsert_wallet_sync,
            telegram_id,
            username,
            first_name,
            bnb_address,
            ton_address,
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("Failed to upsert wallet for %s: %s", telegram_id, exc)
        await chat.send_message("❌ לא הצלחתי לעדכן את הארנק. נסה שוב מאוחר יותר.")
        return

    msg = (
        "✅ הארנק שלך עודכן בהצלחה!\n\n"
        f"Telegram ID: `{wallet.telegram_id}`\n"
        f"BNB/SLH: `{wallet.bnb_address}`\n"
    )
    if wallet.ton_address:
        msg += f"TON: `{wallet.ton_address}`\n"

    msg += "\nכעת תוכל להשתמש ב-/balances כדי לראות את היתרות (בשלב זה 0, בסיס למערכת מלאה)."

    await chat.send_message(msg, parse_mode="Markdown")


async def cmd_balances(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    chat = update.effective_chat
    if user is None or chat is None:
        return

    telegram_id = str(user.id)

    try:
        wallet = await asyncio.to_thread(_get_wallet_sync, telegram_id)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Failed to load wallet for %s: %s", telegram_id, exc)
        await chat.send_message("❌ בעיית תקשורת עם השרת. נסה שוב מאוחר יותר.")
        return

    if wallet is None:
        await chat.send_message(
            "לא נמצא אצלנו ארנק עבור המשתמש הזה.\n"
            "השתמש ב-/wallet כדי לרשום את הארנק שלך."
        )
        return

    # כרגע – כל היתרות 0, רק מציגים את הכתובות.
    text = (
        "📊 יתרות דמו (הקוד מוכן לחיבור לרשת אמיתית):\n\n"
        f"BNB/SLH (BSC): `{wallet.bnb_address}`\n"
    )
    if wallet.ton_address:
        text += f"TON: `{wallet.ton_address}`\n"

    text += "\nBNB: 0.0\nSLH: 0.0\n\nבהמשך נחבר ל-BscScan / RPC + TON כדי לקרוא יתרות אמת."

    await chat.send_message(text, parse_mode="Markdown")


# ---------------------------------------------------------------------------
# Application builder + webhook integration
# ---------------------------------------------------------------------------


async def build_application() -> Application:
    """
    Build and start the Telegram Application for webhook mode.
    """
    logger.info("Building Telegram Application (webhook mode)...")

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

    await app.initialize()
    await app.start()

    # קביעת webhook לכתובת /telegram/webhook
    if settings.base_url:
        webhook_url = settings.base_url.rstrip("/") + "/telegram/webhook"
        logger.info("Setting Telegram webhook to %s", webhook_url)
        await app.bot.set_webhook(webhook_url)
    else:
        logger.warning("BASE_URL not set – Telegram webhook not configured.")

    logger.info("Telegram Application initialized.")
    return app


async def get_application() -> Application:
    """
    מוחזר ה-Application הגלובלי. אם לא קיים – נבנה אותו.
    """
    global _application

    async with _application_lock:
        if _application is None:
            _application = await build_application()
        return _application


@router.post("/webhook")
async def telegram_webhook(
    update_dict: dict = Body(...),
) -> dict:
    """
    נקודת כניסה לעדכוני טלגרם (Webhook).

    Railway מכוון את טלגרם לכתובת:
    {BASE_URL}/telegram/webhook
    """
    app = await get_application()

    try:
        update = Update.de_json(update_dict, app.bot)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Invalid update payload: %s", exc)
        raise HTTPException(status_code=400, detail="Invalid update payload")

    await app.process_update(update)
    return {"ok": True}
