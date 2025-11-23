import logging
from typing import Optional

import httpx
from fastapi import APIRouter, Request
from telegram import Update
from telegram.ext import (
    AIORateLimiter,
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
    """Build the Telegram Application with all handlers attached."""
    if not settings.telegram_bot_token:
        raise RuntimeError("telegram_bot_token not configured")

    application = (
        ApplicationBuilder()
        .token(settings.telegram_bot_token)
        .rate_limiter(AIORateLimiter())
        .build()
    )

    application.add_handler(CommandHandler("start", cmd_start))
    application.add_handler(CommandHandler("wallet", cmd_wallet))
    application.add_handler(CommandHandler("set_wallet", cmd_set_wallet))
    application.add_handler(CommandHandler("balances", cmd_balances))

    return application


async def get_application() -> Application:
    """Singleton-ish accessor so FastAPI + webhooks share the same Application."""
    global _application
    if _application is None:
        logger.info("Building Telegram Application (webhook mode)...")
        _application = await _build_application()
        logger.info("Telegram Application initialized.")
    return _application


def _api_base_url() -> str:
    """
    Resolve the base URL for calling our own API.

    In production we expect settings.base_url to be set (e.g. Railway public URL).
    Fallback is http://localhost:8080 for local/dev usage.
    """
    if settings.base_url:
        return settings.base_url.rstrip("/")
    return "http://localhost:8080"


# ===== Commands =====


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Welcome message + basic help."""
    user = update.effective_user
    if not user or not update.message:
        return

    community_part = ""
    if settings.community_link:
        community_part = f"\n\n🔗 קישור לקהילה: {settings.community_link}"

    text = (
        f"שלום @{user.username or user.first_name or 'חבר'}! 🌐\n\n"
        "ברוך הבא ל-SLH Community Wallet 🚀\n\n"
        "פקודות זמינות:\n"
        "/wallet - רישום/עדכון הארנק שלך\n"
        "/balances - צפייה ביתרות (BNB + SLH מרשת BSC)\n"
        f"{community_part}"
    )
    await update.message.reply_text(text)


async def cmd_wallet(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Explain how to register / update a wallet."""
    if not update.message:
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
    await update.message.reply_text(text)


async def cmd_set_wallet(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Parse /set_wallet and call the API to upsert the wallet."""
    user = update.effective_user
    if not user or not update.message:
        return

    parts = (update.message.text or "").strip().split()
    if len(parts) not in (2, 3):
        await update.message.reply_text(
            "שימוש: /set_wallet <כתובת_BNB>\n"
            "או: /set_wallet <כתובת_BNB> <כתובת_TON>"
        )
        return

    if len(parts) == 2:
        _, bnb_address = parts
        ton_address: Optional[str] = None
    else:
        _, bnb_address, ton_address = parts

    api_base = _api_base_url()
    url = f"{api_base}/api/wallet/set"

    payload = {
        "bnb_address": bnb_address,
        "ton_address": ton_address,
    }

    params = {
        "telegram_id": str(user.id),
        "username": user.username or "",
        "first_name": user.first_name or "",
    }

    logger.info(
        "Sending wallet update to API: url=%s telegram_id=%s bnb=%s ton=%s",
        url,
        params["telegram_id"],
        bnb_address,
        ton_address,
    )

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(url, json=payload, params=params)
        resp.raise_for_status()
    except Exception as e:  # noqa: BLE001
        logger.exception("Failed to update wallet via API: %s", e)
        if update.message:
            await update.message.reply_text(
                "❌ לא הצלחתי לעדכן את הארנק. נסה שוב מאוחר יותר."
            )
        return

    if update.message:
        ton_part = ton_address or "-"
        await update.message.reply_text(
            "✅ הארנק עודכן בהצלחה!\n\n"
            f"BNB/SLH: {bnb_address}\n"
            f"TON: {ton_part}"
        )


async def cmd_balances(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Fetch live balances for the current user from our API
    (which connects to BscScan + חוזה SLH).
    """
    user = update.effective_user
    if not user or not update.message:
        return

    api_base = _api_base_url()
    url = f"{api_base}/api/wallet/{user.id}/balances"

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(url)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:  # noqa: BLE001
        logger.exception("Failed to fetch balances from API: %s", e)
        await update.message.reply_text(
            "❌ לא הצלחתי למשוך יתרות כרגע (BscScan / API). נסה שוב מאוחר יותר."
        )
        return

    bnb_address = data.get("bnb_address") or "-"
    ton_address = data.get("ton_address") or "-"
    bnb_balance = data.get("bnb_balance", 0)
    slh_balance = data.get("slh_balance", 0)

    balances_text = (
        "יתרות ארנק (חיבור חי לרשת BSC):\n\n"
        f"BNB / SLH כתובת: {bnb_address}\n"
        f"TON: {ton_address}\n\n"
        f"BNB balance: {bnb_balance}\n"
        f"SLH balance: {slh_balance}\n\n"
        "הנתונים מחושבים בזמן אמת מ-BscScan עבור החוזה של SLH.\n"
    )

    await update.message.reply_text(balances_text)


# ===== Webhook =====


@router.post("/telegram/webhook")
async def telegram_webhook(request: Request) -> dict:
    """
    Telegram webhook endpoint.

    Telegram will POST updates here; we deserialize them and pass to the shared
    Application instance.
    """
    app = await get_application()
    data = await request.json()
    update = Update.de_json(data, app.bot)
    await app.process_update(update)
    return {"ok": True}
