import logging
from typing import Any, Dict

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from .config import settings
from .db import get_db
from . import models

logger = logging.getLogger("slh.bot")

router = APIRouter()

TELEGRAM_API_BASE = "https://api.telegram.org"


async def send_message(chat_id: int, text: str) -> None:
    if not settings.telegram_bot_token:
        logger.error("TELEGRAM_BOT_TOKEN is not configured")
        return

    url = f"{TELEGRAM_API_BASE}/bot{settings.telegram_bot_token}/sendMessage"
    payload: Dict[str, Any] = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown",
    }

    async with httpx.AsyncClient() as client:
        resp = await client.post(url, json=payload)
        if resp.status_code != 200:
            logger.error("Failed to send message to Telegram: %s %s", resp.status_code, resp.text)


@router.post("/webhook")
async def telegram_webhook(request: Request, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Telegram webhook endpoint.

    Handles:
    - /start
    - /wallet
    - /set_wallet <BNB> <SLH>
    - /balances
    """
    try:
        update = await request.json()
    except Exception as exc:  # noqa: BLE001
        logger.error("Invalid JSON from Telegram: %s", exc)
        raise HTTPException(status_code=400, detail="Invalid JSON")

    message = update.get("message") or update.get("edited_message")
    if not message:
        # Callback / inline / etc. – ignore for now
        return {"ok": True}

    chat = message.get("chat") or {}
    chat_id = chat.get("id")
    text: str = message.get("text") or ""

    if not chat_id or not text:
        return {"ok": True}

    user = message.get("from") or {}
    telegram_id = str(user.get("id"))
    username = user.get("username")
    first_name = user.get("first_name")
    last_name = user.get("last_name")

    # make sure there's at least a basic wallet row
    wallet = db.get(models.Wallet, telegram_id)
    if wallet is None:
        wallet = models.Wallet(
            telegram_id=telegram_id,
            username=username,
            first_name=first_name,
            last_name=last_name,
        )
        db.add(wallet)
        db.commit()
        db.refresh(wallet)

    if text.startswith("/start"):
        await handle_start(chat_id)
    elif text.startswith("/wallet"):
        await handle_wallet(chat_id)
    elif text.startswith("/set_wallet"):
        await handle_set_wallet(chat_id, text, wallet, db)
    elif text.startswith("/balances"):
        await handle_balances(chat_id, wallet)
    else:
        await send_message(
            chat_id,
            "אני מבין כרגע את הפקודות: /start, /wallet, /set_wallet, /balances 🙂",
        )

    return {"ok": True}


async def handle_start(chat_id: int) -> None:
    lines = [
        "שלום וברוך הבא ל-*SLH Community Wallet* 🚀",
        "",
        "פקודות זמינות:",
        "/wallet – רישום/עדכון הארנק שלך",
        "/set_wallet `<כתובת_BNB> <כתובת_SLH>` – שמירת כתובות",
        "/balances – צפייה בפרטי הארנק השמורים",
    ]
    await send_message(chat_id, "\n".join(lines))


async def handle_wallet(chat_id: int) -> None:
    text = (
        "📲 *רישום / עדכון ארנק SLH*\n\n"
        "שלח לי את כתובת ה-BNB ואת כתובת ה-SLH שלך כך:\n"
        "`/set_wallet 0xכתובת_BNB 0xכתובת_SLH`\n\n"
        "אחרי ששמרת כתובות תוכל להשתמש ב-/balances."
    )
    await send_message(chat_id, text)


async def handle_set_wallet(chat_id: int, text: str, wallet: models.Wallet, db: Session) -> None:
    parts = text.split()
    if len(parts) != 3:
        await send_message(
            chat_id,
            "פורמט שגוי.\nדוגמה:\n`/set_wallet 0xBNB 0xSLH`",
        )
        return

    bnb_address, slh_address = parts[1], parts[2]
    wallet.bnb_address = bnb_address
    wallet.slh_address = slh_address
    db.add(wallet)
    db.commit()

    await send_message(chat_id, "✅ הארנק שלך עודכן בהצלחה במערכת.")


async def handle_balances(chat_id: int, wallet: models.Wallet) -> None:
    if not wallet.bnb_address and not wallet.slh_address:
        await send_message(
            chat_id,
            "לא שמורות כרגע כתובות עבורך. השתמש ב-/set_wallet קודם.",
        )
        return

    text = (
        "🏦 *פרטי הארנק השמורים שלך:*\n\n"
        f"BNB: `{wallet.bnb_address or 'לא הוגדר'}`\n"
        f"SLH (BSC): `{wallet.slh_address or 'לא הוגדר'}`\n\n"
        "_יתרות on-chain יתווספו בהמשך._"
    )
    await send_message(chat_id, text)
