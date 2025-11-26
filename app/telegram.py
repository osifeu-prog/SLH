from typing import Any, Dict, Optional

import os
import logging
import httpx
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .config import settings
from .db import get_db
from .models import Wallet
from .wallet import upsert_wallet

router = APIRouter(prefix="/telegram", tags=["telegram"])

logger = logging.getLogger("slh.telegram")

# ---- CONFIG ----

BNB_PRICE_API = (
    "https://api.coingecko.com/api/v3/simple/price"
    "?ids=binancecoin&vs_currencies=usd"
)

# קאש למחיר BNB כדי להימנע מיותר מדי קריאות ל-Coingecko
_BNB_PRICE_CACHE = None
_BNB_PRICE_CACHE_TS = None

# מחיר SLH בדולרים – ניתן להגדיר ב-Railway:
# SLH_USD_PRICE="0.05"  (לדוגמה)
SLH_USD_FALLBACK = float(os.getenv("SLH_USD_PRICE") or "0")


def _api_base_url() -> str:
    """
    בסיס ה-URL לקריאה ל-API הפנימי.
    העדפה: settings.base_url (כפי שהוגדר ב-Railway).
    נפילה: http://localhost:8000 לפיתוח מקומי.
    """
    base = getattr(settings, "base_url", None) or os.getenv(
        "API_BASE_URL", "http://localhost:8000"
    )
    return base.rstrip("/")


# ---- Telegram helpers ----


async def send_message(
    chat_id: int | str,
    text: str,
    reply_markup: Optional[Dict[str, Any]] = None,
    parse_mode: Optional[str] = None,
) -> None:
    """עטיפה נוחה ל-sendMessage עם אפשרות ל-inline keyboard."""
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
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(url, json=payload)
        if resp.status_code != 200:
            logger.warning(
                "Telegram sendMessage failed: %s %s",
                resp.status_code,
                resp.text[:300],
            )
    except Exception as exc:  # noqa: BLE001
        logger.exception("Telegram sendMessage exception: %s", exc)


def _extract_message(update: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """מחפש את האובייקט של ההודעה מתוך update (message / edited_message וכו')."""
    for key in (
        "message",
        "edited_message",
        "channel_post",
        "edited_channel_post",
    ):
        if key in update:
            return update[key]
    return None


# ---- Price helpers ----



async def _fetch_bnb_price_usd() -> float:
    """
    משיכת מחיר BNB/USD מ-Coingecko עם קאשינג בסיסי כדי למנוע 429.
    במידה והקריאה נכשלת – נשתמש בערך הקודם אם קיים, אחרת נחזיר 0.
    """
    global _BNB_PRICE_CACHE, _BNB_PRICE_CACHE_TS

    # אם יש לנו מחיר בקאש מה-5 דקות האחרונות – נחזיר אותו
    try:
        from datetime import datetime, timedelta  # import פנימי כדי לא לשבור קוד קיים
    except Exception:
        datetime = None  # fallback תאורטי

    try:
        if datetime is not None and _BNB_PRICE_CACHE is not None and _BNB_PRICE_CACHE_TS is not None:
            if datetime.utcnow() - _BNB_PRICE_CACHE_TS < timedelta(minutes=5):
                return _BNB_PRICE_CACHE
    except NameError:
        # אם המשתנים עדיין לא הוגדרו
        _BNB_PRICE_CACHE = None
        _BNB_PRICE_CACHE_TS = None

    # אין קאש או שהוא ישן – ננסה למשוך מחדש
    try:
        import httpx as _httpx  # שימוש ב-httpx הקיים
        async with _httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.get(BNB_PRICE_API)
        resp.raise_for_status()
        data = resp.json()
        price = float(data.get("binancecoin", {}).get("usd", 0.0) or 0.0)
        if price > 0:
            _BNB_PRICE_CACHE = price
            if datetime is not None:
                _BNB_PRICE_CACHE_TS = datetime.utcnow()
        return price
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to fetch BNB price from CoinGecko (using cache/fallback): %s", exc)
        try:
            # אם יש לנו ערך בקאש – נחזיר אותו
            return _BNB_PRICE_CACHE or 0.0
        except Exception:
            return 0.0


def _get_slh_price_usd() -> float:
() -> float:
    """
    מחזיר מחיר SLH בדולרים.
    כרגע מתוך ENV: SLH_USD_PRICE.
    אם לא הוגדר – 0.
    """
    return SLH_USD_FALLBACK


def _format_float(value: float, decimals: int = 4) -> str:
    fmt = f"{{:.{decimals}f}}"
    return fmt.format(value)


# ---- API helpers ----


async def _fetch_balances_from_api(telegram_id: str) -> Optional[Dict[str, Any]]:
    """
    קריאה ל-GET /api/wallet/{telegram_id}/balances כדי להביא נתונים חיים מהרשת.
    """
    base_url = _api_base_url()
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


# ---- ROUTES ----


@router.post("/webhook")
async def telegram_webhook(
    update: Dict[str, Any],
    db: Session = Depends(get_db),
):
    """
    Webhook פשוט לבוט הקהילה.
    מנהל את הפקודות:
    /start, /wallet, /set_wallet, /balances
    """
    message = _extract_message(update)
    if not message:
        return {"ok": True}

    text: str = message.get("text") or ""
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

    text = text.strip()

    # ----- /start -----
    if text.startswith("/start"):
        community_link = getattr(settings, "community_link", None) or os.getenv(
            "COMMUNITY_LINK"
        )

        base_text = (
            "שלום @{username}! 🌐\n\n"
            "ברוך הבא ל-SLH Community Wallet 🚀\n\n"
            "פקודות זמינות:\n"
            "/wallet - רישום/עדכון הארנק שלך\n"
            "/balances - צפייה ביתרות החיות על רשת BSC\n"
        )
        if community_link:
            base_text += f"\n🔗 קישור לקהילה: {community_link}"

        await send_message(
            chat_id,
            base_text.format(username=username or telegram_id),
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
            )
            return {"ok": False}

        text_reply = (
            "✅ הארנק עודכן בהצלחה!\n\n"
            f"BNB/SLH: {bnb_address}\n"
            f"TON: {ton_address or '-'}"
        )
        await send_message(chat_id, text_reply)
        return {"ok": True}

    # ----- /balances -----
    if text.startswith("/balances"):
        # 1) נביא את היתרות החיות מה-API שלך (שכבר מחובר ל-BSC)
        balances = await _fetch_balances_from_api(telegram_id)
        if balances is None:
            await send_message(
                chat_id,
                "לא נמצא ארנק למשתמש זה. השתמש ב-/wallet כדי להגדיר ארנק.",
            )
            return {"ok": True}

        bnb_address = balances.get("bnb_address") or "-"
        ton_address = balances.get("ton_address") or "-"
        slh_address = balances.get("slh_address") or bnb_address

        bnb_balance = float(balances.get("bnb_balance", 0.0) or 0.0)
        slh_balance = float(balances.get("slh_balance", 0.0) or 0.0)

        # 2) מחירים בדולרים
        bnb_price_usd = await _fetch_bnb_price_usd()
        slh_price_usd = _get_slh_price_usd()

        bnb_value_usd = bnb_balance * bnb_price_usd
        slh_value_usd = slh_balance * slh_price_usd if slh_price_usd > 0 else 0.0
        total_usd = bnb_value_usd + slh_value_usd

        # 3) טקסט למשתמש
        if slh_price_usd > 0:
            slh_price_line = f"מחיר SLH משוער: ~${_format_float(slh_price_usd, 4)}"
            slh_value_line = f"≈ ${_format_float(slh_value_usd, 2)}"
        else:
            slh_price_line = "מחיר SLH לא מוגדר בשרת (SLH_USD_PRICE)."
            slh_value_line = "N/A"

        balances_text = (
            "יתרות ארנק (חיבור חי ל-BSC):\n\n"
            f"BNB / SLH כתובת: {bnb_address}\n"
            f"TON: {ton_address}\n\n"
            f"BNB balance: {_format_float(bnb_balance, 6)} "
            f"(≈ ${_format_float(bnb_value_usd, 2)})\n"
            f"SLH balance: {_format_float(slh_balance, 4)} "
            f"(≈ {slh_value_line})\n\n"
            "הנתונים מחושבים בזמן אמת מרשת BNB Smart Chain על בסיס הכתובת השמורה בארנק הקהילה.\n\n"
            f"מחיר BNB משוער: ~${_format_float(bnb_price_usd, 2)}\n"
            f"{slh_price_line}\n\n"
            f"≈ שווי כולל (BNB+SLH): ${_format_float(total_usd, 2)}"
        )

        # 4) Inline keyboard – BscScan + MetaMask
        # MetaMask dapp link: יפתח את כתובת BscScan בתוך MetaMask כאפליקציית דפדפן
        keyboard = {
            "inline_keyboard": [
                [
                    {
                        "text": "🔍 פתח ב-BscScan",
                        "url": f"https://bscscan.com/address/{bnb_address}",
                    },
                    {
                        "text": "🦊 פתח ב-MetaMask",
                        "url": f"https://metamask.app.link/dapp/bscscan.com/address/{bnb_address}",
                    },
                ]
            ]
        }

        await send_message(
            chat_id,
            balances_text,
            reply_markup=keyboard,
        )
        return {"ok": True}

    # ----- פקודה לא מוכרת -----
    await send_message(
        chat_id,
        "❓ פקודה לא מוכרת. השתמש ב-/wallet כדי להתחיל.",
    )
    return {"ok": True}
