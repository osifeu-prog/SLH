from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

import httpx
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .config import settings
from .db import get_db
from .models import Wallet
from .wallet import upsert_wallet

router = APIRouter(prefix="/telegram", tags=["telegram"])

logger = logging.getLogger("slh.telegram")

BNB_PRICE_API = (
    "https://api.coingecko.com/api/v3/simple/price"
    "?ids=binancecoin&vs_currencies=usd"
)

# קאש למחיר BNB כדי למנוע יותר מדי קריאות ל-Coingecko
_BNB_PRICE_CACHE: Optional[float] = None
_BNB_PRICE_CACHE_TS: Optional[datetime] = None


def _api_base_url() -> str:
    """
    בסיס ל-API הפנימי.
    קודם מנסה settings.base_url, אחר כך משתנה סביבה BASE_URL.
    """
    return getattr(settings, "base_url", None) or os.getenv("BASE_URL", "").rstrip("/")


async def _fetch_bnb_price_usd() -> float:
    """
    משיכת מחיר BNB/USD מ-Coingecko עם קאשינג כדי להקטין Rate Limit (429).
    במקרה של תקלה – נחזיר את הערך האחרון בקאש (אם קיים), אחרת 0.
    """
    global _BNB_PRICE_CACHE, _BNB_PRICE_CACHE_TS

    if _BNB_PRICE_CACHE is not None and _BNB_PRICE_CACHE_TS is not None:
        if datetime.utcnow() - _BNB_PRICE_CACHE_TS < timedelta(minutes=5):
            return _BNB_PRICE_CACHE

    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.get(BNB_PRICE_API)
        resp.raise_for_status()
        data = resp.json()
        price = float(data.get("binancecoin", {}).get("usd", 0.0) or 0.0)
        if price > 0:
            _BNB_PRICE_CACHE = price
            _BNB_PRICE_CACHE_TS = datetime.utcnow()
        return price
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "Failed to fetch BNB price from CoinGecko (using cache/fallback): %s",
            exc,
        )
        return _BNB_PRICE_CACHE or 0.0


def _get_slh_price_usd() -> float:
    """
    מחיר SLH בדולרים מתוך משתנה סביבה SLH_USD_PRICE (או 0 אם לא הוגדר).
    """
    try:
        return float(os.getenv("SLH_USD_PRICE") or "0")
    except Exception:
        return 0.0


async def send_message(
    chat_id: int | str,
    text: str,
    reply_markup: Optional[Dict[str, Any]] = None,
    parse_mode: Optional[str] = None,
) -> None:
    """
    עטיפה נוחה ל-sendMessage עם אפשרות ל-reply keyboard.
    """
    if not settings.telegram_bot_token:
        logger.warning("telegram_bot_token not configured – cannot send message")
        return

    url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"

    payload: Dict[str, Any] = {"chat_id": chat_id, "text": text}
    if reply_markup is not None:
        payload["reply_markup"] = reply_markup
    if parse_mode:
        payload["parse_mode"] = parse_mode

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url, json=payload)
        if resp.status_code != 200:
            logger.warning(
                "Telegram sendMessage failed: %s %s",
                resp.status_code,
                resp.text,
            )
    except Exception as exc:  # noqa: BLE001
        logger.exception("Error while sending Telegram message: %s", exc)


def _extract_message(update: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    תמיכה ב-update מסוג message / edited_message.
    (כרגע מתעלמים מ-callback_query כדי לשמור את הקוד פשוט.)
    """
    if "message" in update:
        return update["message"]
    if "edited_message" in update:
        return update["edited_message"]
    return None


async def _fetch_balances_from_api(telegram_id: str) -> Optional[Dict[str, Any]]:
    """
    קריאה ל-GET /api/wallet/{telegram_id}/balances כדי להביא נתונים חיים מהרשת.
    """
    base_url = _api_base_url()
    if not base_url:
        logger.warning("BASE_URL not configured – cannot call balances API")
        return None

    url = f"{base_url}/api/wallet/{telegram_id}/balances"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url)
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        data = resp.json()
        logger.info("Balances API response for %s: %s", telegram_id, data)
        return data
    except Exception as exc:  # noqa: BLE001
        logger.exception("Failed to fetch balances from API: %s", exc)
        return None


@router.post("/webhook")
async def telegram_webhook(
    update: Dict[str, Any],
    db: Session = Depends(get_db),
):
    """
    Webhook פשוט לבוט הקהילה.
    מנהל את הפקודות:
    /start, /wallet, /set_wallet, /balances, /send_slh
    """
    message = _extract_message(update)
    if not message:
        return {"ok": True}

    text: str = (message.get("text") or "").strip()
    chat = message.get("chat") or {}
    from_user = message.get("from") or {}

    chat_id = chat.get("id")
    telegram_id = (
        str(from_user.get("id")) if from_user.get("id") is not None else None
    )
    username = from_user.get("username")
    first_name = from_user.get("first_name")

    if not chat_id or not telegram_id:
        return {"ok": False}

    # מקלדת ברירת מחדל
    default_keyboard: Dict[str, Any] = {
        "keyboard": [
            [{"text": "/wallet"}, {"text": "/balances"}],
            [{"text": "/send_slh 10 @username"}],
        ],
        "resize_keyboard": True,
        "one_time_keyboard": False,
    }

    # ----- /start -----
    if text.startswith("/start"):
        community_link = getattr(settings, "community_link", None) or os.getenv(
            "COMMUNITY_LINK"
        )

        base_text = (
            f"שלום @{username or telegram_id}! 🌐\n\n"
            "ברוך הבא ל-SLH Community Wallet 🚀\n\n"
            "פקודות זמינות:\n"
            "/wallet - רישום/עדכון הארנק שלך\n"
            "/balances - צפייה ביתרות החיות על רשת BSC\n"
            "/send_slh <amount> <@username|telegram_id> - העברת SLH וירטואלית בין משתמשי הקהילה\n"
        )
        if community_link:
            base_text += f"\n🔗 קישור לקהילה: {community_link}"

        await send_message(
            chat_id,
            base_text,
            reply_markup=default_keyboard,
        )
        return {"ok": True}

    # ----- /wallet -----
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
            reply_markup=default_keyboard,
        )
        return {"ok": True}

    # ----- /set_wallet -----
    if text.startswith("/set_wallet"):
        parts = text.split()
        args = parts[1:]
        if len(args) == 0:
            await send_message(
                chat_id,
                "שימוש: /set_wallet <כתובת_BNB> [כתובת_TON]",
                reply_markup=default_keyboard,
            )
            return {"ok": True}

        bnb_address = args[0].strip()
        ton_address = args[1].strip() if len(args) > 1 else None

        try:
            upsert_wallet(
                db=db,
                telegram_id=telegram_id,
                username=username,
                first_name=first_name,
                bnb_address=bnb_address,
                ton_address=ton_address,
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("Failed to upsert wallet: %s", exc)
            await send_message(
                chat_id,
                "❌ לא הצלחתי לעדכן את הארנק. נסה שוב מאוחר יותר.",
                reply_markup=default_keyboard,
            )
            return {"ok": False}

        text_reply = (
            "✅ הארנק עודכן בהצלחה!\n\n"
            f"BNB/SLH: {bnb_address}\n"
            f"TON: {ton_address or '-'}"
        )
        await send_message(chat_id, text_reply, reply_markup=default_keyboard)
        return {"ok": True}

    # ----- /balances -----
    if text.startswith("/balances"):
        balances = await _fetch_balances_from_api(telegram_id)
        if balances is None:
            await send_message(
                chat_id,
                "לא נמצא ארנק למשתמש זה. השתמש ב-/wallet כדי להגדיר ארנק.",
                reply_markup=default_keyboard,
            )
            return {"ok": True}

        bnb_address = balances.get("bnb_address") or "-"
        ton_address = balances.get("ton_address") or "-"
        slh_address = balances.get("slh_address") or bnb_address

        bnb_balance = float(balances.get("bnb_balance", 0.0) or 0.0)
        slh_balance = float(balances.get("slh_balance", 0.0) or 0.0)

        bnb_price_usd = await _fetch_bnb_price_usd()
        slh_price_usd = _get_slh_price_usd()

        bnb_value_usd = bnb_balance * bnb_price_usd
        slh_value_usd = slh_balance * slh_price_usd if slh_price_usd > 0 else 0.0
        total_usd = bnb_value_usd + slh_value_usd

        lines = [
            "📊 יתרות ארנק (חי מ-BSC):",
            "",
            f"BNB / SLH כתובת: {bnb_address}",
            f"TON: {ton_address or '-'}",
            "",
            f"BNB: {bnb_balance:.6f} (~${bnb_value_usd:,.2f})",
            f"SLH: {slh_balance:.4f}"
            + (f" (~${slh_value_usd:,.2f})" if slh_price_usd > 0 else ""),
            "",
            f"≈ שווי כולל (BNB+SLH): ~${total_usd:,.2f}",
        ]

        await send_message(
            chat_id,
            "\n".join(lines),
            reply_markup=default_keyboard,
        )
        return {"ok": True}

    # ----- /send_slh -----
    if text.startswith("/send_slh"):
        parts = text.split()
        args = parts[1:]
        if len(args) < 2:
            await send_message(
                chat_id,
                "שימוש: /send_slh <amount> <@username|telegram_id> [הערה]",
                reply_markup=default_keyboard,
            )
            return {"ok": True}

        amount_raw = args[0]
        target_raw = args[1]
        note = " ".join(args[2:]) if len(args) > 2 else None

        try:
            amount = float(amount_raw)
            if amount <= 0:
                raise ValueError("amount must be positive")
        except Exception:
            await send_message(
                chat_id,
                "❌ סכום לא חוקי. השתמש לדוגמה: /send_slh 100 @username",
                reply_markup=default_keyboard,
            )
            return {"ok": True}

        from_wallet = db.get(Wallet, telegram_id)
        if not from_wallet:
            await send_message(
                chat_id,
                "אין לך ארנק מוגדר. השתמש ב-/wallet כדי להגדיר ארנק לפני העברה.",
                reply_markup=default_keyboard,
            )
            return {"ok": True}

        # חיפוש נמען לפי username או לפי telegram_id
        to_wallet: Optional[Wallet]
        if target_raw.startswith("@"):
            target_username = target_raw[1:]
            to_wallet = (
                db.query(Wallet)
                .filter(Wallet.username == target_username)
                .first()
            )
            to_label = f"@{target_username}"
        else:
            to_wallet = db.get(Wallet, target_raw)
            to_label = f"user_id={target_raw}"

        if not to_wallet:
            await send_message(
                chat_id,
                "❌ לא נמצא נמען עם הנתון שסיפקת. ודא שיש לו ארנק בקהילה (פקודת /wallet).",
                reply_markup=default_keyboard,
            )
            return {"ok": True}

        # בשלב זה ההעברה היא וירטואלית בלבד – רישום לוג בלבד ללא שינוי on-chain
        logger.info(
            "Simulated internal transfer: from=%s to=%s amount=%s note=%s",
            telegram_id,
            to_wallet.telegram_id,
            amount,
            note,
        )

        confirm_text_sender = (
            "✅ בקשת העברה התקבלה!\n\n"
            f"שלחת (וירטואלי בשלב זה) {amount} SLH אל {to_label}.\n"
        )
        if note:
            confirm_text_sender += f"\nהערה: {note}"

        await send_message(
            chat_id,
            confirm_text_sender,
            reply_markup=default_keyboard,
        )

        # הודעה לנמען (אם מדובר בצ'אט פרטי רגיל)
        try:
            await send_message(
                to_wallet.telegram_id,
                (
                    "📥 קיבלת העברת SLH וירטואלית מהקהילה!\n\n"
                    f"שולח: @{username or telegram_id}\n"
                    f"סכום: {amount} SLH\n"
                    + (f"\nהערה: {note}" if note else "")
                ),
                reply_markup=default_keyboard,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to notify recipient about transfer: %s", exc)

        return {"ok": True}

    # ----- פקודה לא מוכרת -----
    await send_message(
        chat_id,
        "❓ פקודה לא מוכרת. השתמש ב-/wallet כדי להתחיל.",
        reply_markup=default_keyboard,
    )
    return {"ok": True}
