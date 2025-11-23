from typing import Any, Dict, Optional

import httpx
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .config import settings
from .db import get_db
from .models import Wallet
from .routers.wallet import upsert_wallet, get_balances_live

router = APIRouter(prefix="/telegram", tags=["telegram"])


async def send_message(chat_id: int | str, text: str, parse_mode: Optional[str] = "Markdown") -> None:
    """
    Helper לשליחת הודעות לטלגרם.
    אם אין טוקן – לא עושה כלום (מגן מפני קונפיג לא מלא).
    """
    if not settings.telegram_bot_token:
        return

    url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"
    payload: Dict[str, Any] = {
        "chat_id": chat_id,
        "text": text,
    }
    if parse_mode:
        payload["parse_mode"] = parse_mode
        payload["disable_web_page_preview"] = True

    async with httpx.AsyncClient(timeout=10) as client:
        await client.post(url, json=payload)


def _extract_message(update: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    מחלץ את אובייקט ה-message מתוך ה-update של טלגרם
    (message / edited_message / channel_post וכו').
    """
    for key in ("message", "edited_message", "channel_post", "edited_channel_post"):
        if key in update:
            return update[key]
    return None


@router.post("/webhook")
async def telegram_webhook(
    update: Dict[str, Any],
    db: Session = Depends(get_db),
):
    """
    Webhook יחיד לטלגרם – מטפל בכל הפקודות של הבוט.
    """
    message = _extract_message(update)
    if not message:
        return {"ok": True}

    text: str = (message.get("text") or "").strip()
    chat = message.get("chat") or {}
    from_user = message.get("from") or {}

    chat_id = chat.get("id")
    telegram_id = str(from_user.get("id")) if from_user.get("id") is not None else None
    username = from_user.get("username")
    first_name = from_user.get("first_name")

    if not chat_id or not telegram_id:
        return {"ok": False}

    # -------- /start --------
    if text.startswith("/start"):
        community_part = ""
        if getattr(settings, "community_link", None):
            community_part = f"\n\n🔗 קישור לקהילה: {settings.community_link}"

        await send_message(
            chat_id,
            (
                "שלום @{username}! 🌐\n\n"
                "ברוך הבא ל-SLH Community Wallet 🚀\n\n"
                "פקודות זמינות:\n"
                "/wallet - רישום/עדכון הארנק שלך\n"
                "/balances - צפייה ביתרות האמיתיות שלך (BNB + SLH על BSC)"
                "{community_part}"
            ).format(username=username or telegram_id, community_part=community_part),
        )
        return {"ok": True}

    # -------- /wallet --------
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

    # -------- /set_wallet --------
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

        text_lines = [
            "✅ הארנק שלך עודכן בהצלחה!",
            "",
            f"BNB / SLH: `{bnb_address}`",
        ]
        if ton_address:
            text_lines.append(f"TON: `{ton_address}`")

        await send_message(chat_id, "\n".join(text_lines))
        return {"ok": True}

    # -------- /balances --------
    if text.startswith("/balances"):
        wallet: Optional[Wallet] = db.get(Wallet, telegram_id)
        if wallet is None:
            await send_message(
                chat_id,
                "לא נמצא ארנק למשתמש זה. השתמש ב-/wallet כדי להגדיר ארנק.",
            )
            return {"ok": True}

        # שימוש בפונקציה שחיה בשרת ומתחברת ל-BscScan
        try:
            balances = await get_balances_live(wallet)
        except Exception:
            await send_message(
                chat_id,
                "❌ לא הצלחתי למשוך כעת את היתרות מהרשת. נסה שוב מאוחר יותר.",
            )
            return {"ok": False}

        balances_text = (
            "יתרות ארנק (חיבור חי לרשת BSC):\n\n"
            f"BNB / SLH כתובת: `{balances.bnb_address or '-'}`\n"
            f"TON: `{balances.ton_address or '-'}`\n\n"
            f"BNB balance: {balances.bnb_balance}\n"
            f"SLH balance: {balances.slh_balance}\n\n"
            "הנתונים מחושבים בזמן אמת מ-BscScan עבור החוזה של SLH.\n"
        )

        await send_message(chat_id, balances_text)
        return {"ok": True}

    # -------- פקודה לא מוכרת --------
    await send_message(
        chat_id,
        "❓ פקודה לא מוכרת.\n"
        "פקודות זמינות:\n"
        "/wallet - הגדרת ארנק\n"
        "/balances - בדיקת יתרות על הרשת",
    )
    return {"ok": True}
