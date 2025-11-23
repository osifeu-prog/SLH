from typing import Any, Dict, Optional

import httpx
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .config import settings
from .db import get_db
from .models import Wallet
from .wallet import upsert_wallet

router = APIRouter(prefix="/telegram", tags=["telegram"])


async def send_message(chat_id: int | str, text: str) -> None:
    if not settings.telegram_bot_token:
        return
    url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"
    async with httpx.AsyncClient(timeout=10) as client:
        await client.post(url, json={"chat_id": chat_id, "text": text})


def _extract_message(update: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    for key in ("message", "edited_message", "channel_post", "edited_channel_post"):
        if key in update:
            return update[key]
    return None


@router.post("/webhook")
async def telegram_webhook(
    update: Dict[str, Any],
    db: Session = Depends(get_db),
):
    message = _extract_message(update)
    if not message:
        return {"ok": True}

    text: str = message.get("text") or ""
    chat = message.get("chat") or {}
    from_user = message.get("from") or {}

    chat_id = chat.get("id")
    telegram_id = str(from_user.get("id")) if from_user.get("id") is not None else None
    username = from_user.get("username")
    first_name = from_user.get("first_name")

    if not chat_id or not telegram_id:
        return {"ok": False}

    text = text.strip()

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
        args = parts[1:]
        if len(args) == 0:
            await send_message(
                chat_id,
                "שימוש: /set_wallet <כתובת_BNB> [כתובת_TON]",
            )
            return {"ok": True}

        bnb_address = args[0]
        ton_address = args[1] if len(args) > 1 else None

        try:
            upsert_wallet(
                db=db,
                telegram_id=telegram_id,
                username=username,
                first_name=first_name,
                bnb_address=bnb_address,
                ton_address=ton_address,
            )
        except Exception:
            await send_message(
                chat_id,
                "❌ לא הצלחתי לעדכן את הארנק. נסה שוב מאוחר יותר.",
            )
            return {"ok": False}

        await send_message(
            chat_id,
            "✅ הארנק שלך עודכן בהצלחה!\n"
            f"BNB / SLH: `{bnb_address}`\n"
            + (f"TON: `{ton_address}`" if ton_address else ""),
        )
        return {"ok": True}

    if text.startswith("/balances"):
        wallet: Optional[Wallet] = db.get(Wallet, telegram_id)
        if wallet is None:
            await send_message(
                chat_id,
                "לא נמצא ארנק למשתמש זה. השתמש ב-/wallet כדי להגדיר ארנק.",
            )
            return {"ok": True}

        await send_message(
            chat_id,
            (
                "📊 יתרות SLH Wallet (כרגע ערכים לוגיים בלבד):\n\n"
                f"BNB / SLH address: `{wallet.bnb_address}`\n"
                f"TON address: `{wallet.ton_address or '-'}'\n"
                "\nיתרות רשת (on-chain) יתווספו בשלב הבא דרך BscScan / TON APIs."
            ),
        )
        return {"ok": True}

    # פקודה לא מוכרת
    await send_message(
        chat_id,
        "❓ פקודה לא מוכרת. השתמש ב-/wallet כדי להתחיל.",
    )
    return {"ok": True}
