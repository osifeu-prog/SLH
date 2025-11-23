
import logging
from typing import Any, Dict

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from .config import get_settings
from .db import get_db
from . import models

logger = logging.getLogger("slh.telegram")

router = APIRouter(prefix="/telegram", tags=["telegram"])

settings = get_settings()

def get_bot_api_url(method: str) -> str:
    if not settings.TELEGRAM_BOT_TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is not set")
    return f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/{method}"

async def send_message(chat_id: int, text: str) -> None:
    url = get_bot_api_url("sendMessage")
    async with httpx.AsyncClient(timeout=10) as client:
        try:
            resp = await client.post(url, json={"chat_id": chat_id, "text": text})
            resp.raise_for_status()
        except Exception as e:
            logger.error("Failed to send Telegram message: %s", e)

@router.post("/webhook")
async def telegram_webhook(
    request: Request,
    db: Session = Depends(get_db),
):
    update: Dict[str, Any] = await request.json()
    message = update.get("message") or update.get("edited_message")
    if not message:
        return {"ok": True}

    chat = message.get("chat", {})
    chat_id = chat.get("id")
    from_user = message.get("from", {}) or {}
    text = (message.get("text") or "").strip()

    if not chat_id or not text:
        return {"ok": True}

    telegram_id = str(from_user.get("id", chat_id))
    username = from_user.get("username")
    first_name = from_user.get("first_name")

    # --- Command routing ---
    if text.startswith("/start"):
        await send_message(
            chat_id,
            (
                "שלום @{username}! 🌐\n\n"
                "ברוך הבא ל-SLH Community Wallet 🚀\n\n"
                "פקודות זמינות:\n"
                "/wallet - רישום/עדכון הארנק שלך\n"
                "/balances - צפייה ביתרות (כרגע 0, בסיס לממשק עתידי)"
            ).format(username=username or telegram_id),
        )
        return {"ok": True}

    if text.startswith("/wallet"):
        await send_message(
            chat_id,
            (
                "📲 רישום / עדכון ארנק SLH\n\n"
                "שלח לי את כתובת ה-BNB שלך (אותה כתובת משמשת גם למטבע SLH):\n"
                "/set_wallet <כתובת_BNB>\n\n"
                "אם כבר יש לך גם ארנק TON, אתה יכול להוסיף אותו:\n"
                "/set_wallet <כתובת_BNB> <כתובת_TON>\n\n"
                "דוגמה:\n"
                "/set_wallet 0xd0617b54fb4b6b66307846f217b4d685800e3da4\n"
                "/set_wallet 0xd0617b54fb4b6b66307846f217b4d685800e3da4 UQCXXXXX..."
            ),
        )
        return {"ok": True}

    if text.startswith("/set_wallet"):
        parts = text.split()
        if len(parts) not in (2, 3):
            await send_message(
                chat_id,
                "שימוש: /set_wallet <כתובת_BNB> או /set_wallet <כתובת_BNB> <כתובת_TON>",
            )
            return {"ok": True}

        bnb_address = parts[1]
        ton_address = parts[2] if len(parts) == 3 else None

        wallet = db.get(models.Wallet, telegram_id)
        if wallet is None:
            wallet = models.Wallet(
                telegram_id=telegram_id,
                username=username,
                first_name=first_name,
                bnb_address=bnb_address,
                ton_address=ton_address,
                slh_address=bnb_address,
            )
            db.add(wallet)
        else:
            wallet.username = username or wallet.username
            wallet.first_name = first_name or wallet.first_name
            wallet.bnb_address = bnb_address
            wallet.ton_address = ton_address
            wallet.slh_address = bnb_address

        db.commit()

        await send_message(
            chat_id,
            "✅ הארנק עודכן בהצלחה!\n\nBNB/SLH: {bnb}\nTON: {ton}".format(
                bnb=bnb_address,
                ton=ton_address or "-",
            ),
        )
        return {"ok": True}

    if text.startswith("/balances"):
        wallet = db.get(models.Wallet, telegram_id)
        if wallet is None:
            await send_message(
                chat_id,
                "לא נמצא ארנק עבור המשתמש שלך. שלח /wallet כדי לרשום אחד.",
            )
            return {"ok": True}

        await send_message(
            chat_id,
            (
                "יתרות ארנק (דמו):\n\n"
                "BNB / SLH כתובת: {bnb}\n"
                "TON: {ton}\n\n"
                "BNB balance: 0\n"
                "SLH balance: 0\n\n"
                "בהמשך נחבר ל-BscScan ו-TON לקבלת נתונים אמיתיים."
            ).format(
                bnb=wallet.bnb_address,
                ton=wallet.ton_address or "-",
            ),
        )
        return {"ok": True}

    # Default: ignore or send help
    await send_message(
        chat_id,
        "לא זיהיתי את הפקודה. נסה /start או /wallet.",
    )
    return {"ok": True}
