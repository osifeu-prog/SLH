import logging
import os
from typing import Optional, Any, Dict

import httpx
from fastapi import APIRouter, Request

from .config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/telegram", tags=["telegram"])

TELEGRAM_API_BASE = f"https://api.telegram.org/bot{settings.telegram_bot_token}"

SLH_USD_FALLBACK = float(os.getenv("SLH_USD_PRICE") or "0")
SLH_ILS_FALLBACK = float(os.getenv("SLH_ILS_PRICE") or "444.44")


# ============================
#   Helpers
# ============================


def _api_base_url() -> str:
    """
    בסיס ה-API הפנימי שלנו – משמש לקריאות:
    /api/wallet/set
    /api/wallet/{telegram_id}/balances
    """
    base = (
        settings.API_BASE_URL
        or settings.FRONTEND_API_BASE
        or settings.BASE_URL
    )
    return (base or "").rstrip("/")


def _format_float(value: float, decimals: int = 2) -> str:
    fmt = f"{{:.{decimals}f}}"
    return fmt.format(value)


async def _telegram_post(method: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    url = f"{TELEGRAM_API_BASE}/{method}"
    async with httpx.AsyncClient(timeout=10.0) as client:
        r = await client.post(url, json=payload)
        r.raise_for_status()
        data = r.json()
        if not data.get("ok"):
            logger.error("Telegram API error: %s", data)
        return data


async def send_message(
    chat_id: int,
    text: str,
    parse_mode: Optional[str] = None,
    disable_web_page_preview: bool = False,
) -> None:
    if not settings.telegram_bot_token:
        logger.warning("send_message called but TELEGRAM_BOT_TOKEN is missing")
        return

    payload: Dict[str, Any] = {
        "chat_id": chat_id,
        "text": text,
        "disable_web_page_preview": disable_web_page_preview,
    }
    if parse_mode:
        payload["parse_mode"] = parse_mode

    try:
        await _telegram_post("sendMessage", payload)
    except Exception:
        logger.exception("Failed to send Telegram message")


async def _fetch_bnb_price_usd() -> float:
    """
    מביא מחיר BNB ב-USD (אפשר להחליף למקור אחר בעתיד).
    במקרה כשל – מחזיר 0 כדי שלא יפיל את כל הזרימה.
    """
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(
                "https://api.coingecko.com/api/v3/simple/price",
                params={"ids": "binancecoin", "vs_currencies": "usd"},
            )
            r.raise_for_status()
            data = r.json()
            return float(data["binancecoin"]["usd"])
    except Exception:
        logger.exception("Failed to fetch BNB price, falling back to 0")
        return 0.0


def _get_slh_price_usd() -> float:
    """
    מחיר SLH ב-USD (אם תרצה להשתמש בעתיד).
    כרגע נשען על ENV SLH_USD_PRICE או 0.
    """
    return SLH_USD_FALLBACK


async def _api_get_wallet_balances(telegram_id: int) -> Dict[str, Any]:
    """
    קריאה ל-API הפנימי:
    GET /api/wallet/{telegram_id}/balances
    """
    base = _api_base_url()
    url = f"{base}/api/wallet/{telegram_id}/balances"
    async with httpx.AsyncClient(timeout=10.0) as client:
        r = await client.get(url)
        r.raise_for_status()
        return r.json()


async def _api_set_wallet(
    telegram_id: int,
    bnb_address: str,
    ton_address: Optional[str] = None,
) -> Dict[str, Any]:
    """
    קריאה ל-API הפנימי:
    POST /api/wallet/set
    Body: { telegram_id, bnb_address, ton_address }
    """
    base = _api_base_url()
    url = f"{base}/api/wallet/set"
    payload = {
        "telegram_id": str(telegram_id),
        "bnb_address": bnb_address,
        "ton_address": ton_address,
    }
    async with httpx.AsyncClient(timeout=10.0) as client:
        r = await client.post(url, json=payload)
        r.raise_for_status()
        return r.json()


async def _notify_admin_management_request(
    telegram_id: int,
    username: Optional[str],
    chat_id: int,
) -> None:
    """שולח אליך לוג על בקשת ניהול חדשה."""
    admin_chat_id = settings.ADMIN_LOG_CHAT_ID or os.getenv("ADMIN_LOG_CHAT_ID")
    if not admin_chat_id:
        return

    text = (
        "📥 בקשת גישת ניהול חדשה\n\n"
        f"🔹 User: @{username or 'unknown'}\n"
        f"🔹 telegram_id: {telegram_id}\n"
        f"🔹 chat_id: {chat_id}\n\n"
        "המשתמש הפעיל את /admin וביקש להצטרף לצוות הניהול."
    )

    try:
        await send_message(int(admin_chat_id), text)
    except Exception:
        logger.exception("Failed to send admin management request log")


# ============================
#   Webhook Route
# ============================


@router.post("/webhook")
async def telegram_webhook(request: Request) -> Dict[str, Any]:
    update = await request.json()
    logger.debug("Telegram update received: %s", update)

    message = update.get("message") or update.get("edited_message") or {}
    if not message:
        return {"ok": True}

    chat = message.get("chat") or {}
    from_user = message.get("from") or {}

    chat_id = chat.get("id")
    telegram_id = from_user.get("id")
    username = from_user.get("username")

    if chat_id is None or telegram_id is None:
        logger.warning("Missing chat_id or telegram_id in update")
        return {"ok": True}

    text: str = (message.get("text") or "").strip()

    # ----- /start -----
    if text.startswith("/start"):
        community_link = (
            settings.COMMUNITY_LINK
            or os.getenv("COMMUNITY_LINK")
            or "https://t.me/+HIzvM8sEgh1kNWY0"
        )

        base_text = (
            f"שלום @{username or telegram_id}! 🌐\n\n"
            "ברוך הבא ל-SLH Community Wallet 🚀\n\n"
            "פקודות זמינות:\n"
            "/wallet - רישום/עדכון הארנק שלך\n"
            "/balances - צפייה ביתרות החיות על רשת BSC\n"
            "/admin - בקשת גישת ניהול במערכת\n"
        )

        extra = (
            f"\n🔗 קישור לקהילה: {community_link}\n"
            "הצטרף כדי לקבל גישה מלאה, תמריצים וכלי ניהול קהילה מתקדמים.\n"
        )

        await send_message(chat_id, base_text + extra)
        return {"ok": True}

    # ----- /wallet -----
    if text.startswith("/wallet"):
        help_text = (
            "📲 רישום / עדכון ארנק SLH\n\n"
            "שלח לי את כתובת ה-BNB שלך (אותה כתובת משמשת גם למטבע SLH):\n"
            "/set_wallet <כתובת_BNB>\n\n"
            "אם כבר יש לך גם ארנק TON, אתה יכול להוסיף אותו:\n"
            "/set_wallet <כתובת_BNB> <כתובת_TON>\n\n"
            "דוגמה:\n"
            "/set_wallet 0xd0617b54fb4b6b66307846f217b4d685800e3da4\n"
            "/set_wallet 0xd0617b54fb4b6b66307846f217b4d685800e3da4 UQCXXXXX...\n"
        )
        await send_message(chat_id, help_text)
        return {"ok": True}

    # ----- /set_wallet -----
    if text.startswith("/set_wallet"):
        parts = text.split()
        if len(parts) < 2:
            await send_message(
                chat_id,
                "⚠ שימוש: /set_wallet <כתובת_BNB> [כתובת_TON]\n"
                "דוגמה:\n"
                "/set_wallet 0x1234...\n"
                "/set_wallet 0x1234... UQXXXXX...",
            )
            return {"ok": True}

        bnb_address = parts[1].strip()
        ton_address = parts[2].strip() if len(parts) >= 3 else None

        try:
            await _api_set_wallet(telegram_id=telegram_id, bnb_address=bnb_address, ton_address=ton_address)
        except Exception:
            logger.exception("Failed to set wallet via API")
            await send_message(
                chat_id,
                "❌ שגיאה בשמירת הארנק. נסה שוב מאוחר יותר.",
            )
            return {"ok": True}

        confirm_text = (
            "✅ הארנק עודכן בהצלחה!\n\n"
            f"BNB/SLH: {bnb_address}\n"
            f"TON: {ton_address or '-'}"
        )
        await send_message(chat_id, confirm_text)
        return {"ok": True}

    # ----- /balances -----
    if text.startswith("/balances"):
        try:
            data = await _api_get_wallet_balances(telegram_id)
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                await send_message(
                    chat_id,
                    "לא נמצא ארנק עבור המשתמש הזה.\n"
                    "השתמש ב-/wallet כדי להגדיר ארנק קודם.",
                )
                return {"ok": True}
            logger.exception("Failed to fetch balances from API")
            await send_message(
                chat_id,
                "❌ שגיאה בשליפת היתרות. נסה שוב מאוחר יותר.",
            )
            return {"ok": True}
        except Exception:
            logger.exception("Failed to fetch balances from API")
            await send_message(
                chat_id,
                "❌ שגיאה בשליפת היתרות. נסה שוב מאוחר יותר.",
            )
            return {"ok": True}

        bnb_address = data.get("bnb_address") or "-"
        ton_address = data.get("ton_address") or "-"

        bnb_balance = float(data.get("bnb_balance") or 0.0)
        slh_balance = float(data.get("slh_balance") or 0.0)

        # 2) מחירים בדולרים (BNB) + מחיר קבוע ל-SLH בשקלים
        bnb_price_usd = await _fetch_bnb_price_usd()
        slh_price_usd = _get_slh_price_usd()

        bnb_value_usd = bnb_balance * bnb_price_usd
        slh_value_usd = slh_balance * slh_price_usd if slh_price_usd > 0 else 0.0
        total_usd = bnb_value_usd + slh_value_usd

        # מחיר SLH קבוע במונחי ₪ – "מספר ההצלחה"
        slh_price_ils = getattr(settings, "slh_ils_price", None) or SLH_ILS_FALLBACK
        slh_value_ils = slh_balance * slh_price_ils

        slh_price_line = (
            f"מחיר SLH קבוע במערכת: ~₪{_format_float(slh_price_ils, 2)}"
        )
        if slh_balance > 0:
            slh_value_line = f"≈ ₪{_format_float(slh_value_ils, 2)}"
        else:
            slh_value_line = "≈ ₪0.00"

        balances_text = (
            "יתרות ארנק (חיבור חי ל-BSC):\n\n"
            f"BNB / SLH כתובת: {bnb_address}\n"
            f"TON: {ton_address}\n\n"
            f"BNB balance: {_format_float(bnb_balance, 6)} "
            f"(≈ ${_format_float(bnb_value_usd, 2)})\n"
            f"SLH balance: {_format_float(slh_balance, 4)} "
            f"({slh_value_line})\n\n"
            "הנתונים מחושבים בזמן אמת מרשת BNB Smart Chain על בסיס הכתובת השמורה בארנק הקהילה.\n\n"
            f"מחיר BNB משוער: ~${_format_float(bnb_price_usd, 2)}\n"
            f"{slh_price_line}\n\n"
            f"≈ שווי כולל (BNB+SLH): ${_format_float(total_usd, 2)}"
        )

        await send_message(chat_id, balances_text)
        return {"ok": True}

    # ----- /admin -----
    if text.startswith("/admin"):
        await send_message(
            chat_id,
            (
                "🧩 בקשת ניהול במערכת SLHNET\n\n"
                "איזה תחום ניהול הכי מדבר אליך?\n\n"
                "1. ניהול קהילה 👥\n"
                "2. ניהול תוכן 📝\n"
                "3. ניהול פיננסי 💰\n"
                "4. ניהול טכני / פיתוח 🛠️\n"
                "5. אקדמיה ומומחים 🎓\n\n"
                "ענה כאן במספר או במילים חופשיות, "
                "ואנחנו נבחן את הבקשה שלך וניתן לך מסלול קידום ותמריצים מותאם. 🚀"
            ),
        )

        await _notify_admin_management_request(
            telegram_id=telegram_id,
            username=username,
            chat_id=chat_id,
        )

        return {"ok": True}

    # ----- Fallback -----
    await send_message(
        chat_id,
        "לא זיהיתי את הפקודה.\n"
        "נסה אחת מהפקודות:\n"
        "/wallet, /balances, /admin",
    )
    return {"ok": True}
