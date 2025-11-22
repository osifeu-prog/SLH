import json
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Request, Depends
from telegram import Update
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
)
from sqlalchemy.orm import Session

from .config import settings
from .db import get_db
from . import models

logger = logging.getLogger("slh_wallet.bot")

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
    app.add_handler(CommandHandler("set_bnb", cmd_set_bnb))
    app.add_handler(CommandHandler("set_ton", cmd_set_ton))
    app.add_handler(CommandHandler("help", cmd_help))

    return app


async def get_application() -> Application:
    global _application
    if _application is None:
        _application = await _build_application()
        await _application.initialize()
    return _application


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not user:
        return

    base = settings.base_url

    text = (
        f"שלום @{user.username or user.id}! 🌐\n\n"
        "ברוך הבא לארנק הקהילתי של SLH על רשת BNB.\n\n"
        "כאן אתה יכול: \n"
        "• לרשום את כתובת הארנק שלך ברשת BNB\n"
        "• לרשום כתובת TON לקבלת SLH בטון\n"
        "• לקבל קישור לאזור האישי שלך באתר\n\n"
        "🔐 אין סיסמאות, אין התחברות – הזיהוי הוא דרך טלגרם + כתובות הארנק שלך.\n\n"
        "הפקודות הזמינות:\n"
        "/wallet – יצירת כרטיס משתמש וקבלת קישור אישי\n"
        "/set_bnb <כתובת> – שמירת כתובת BNB שלך\n"
        "/set_ton <כתובת> – שמירת כתובת TON שלך\n"
        "/help – עזרה והסבר מלא\n\n"
        f"אזור אישי יוצג בכתובת: {base}/u/{{telegram_id}}"
    )

    await update.effective_chat.send_message(text)


async def _ensure_wallet_record(user, db: Session) -> models.Wallet:
    wallet = db.get(models.Wallet, str(user.id))
    if not wallet:
        wallet = models.Wallet(
            telegram_id=str(user.id),
            username=user.username or "",
            first_name=user.first_name or "",
            last_name=user.last_name or "",
        )
        db.add(wallet)
        db.commit()
        db.refresh(wallet)
    return wallet


async def cmd_wallet(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not user:
        return

    from .db import SessionLocal

    db = SessionLocal()
    try:
        wallet = await _ensure_wallet_record(user, db)
    finally:
        db.close()

    base = settings.base_url
    hub_url = f"{base}/u/{user.id}"

    text = (
        "📲 *הכרטיס הקהילתי שלך מוכן!*\n\n"
        "המערכת מזהה אותך לפי טלגרם בלבד ושומרת רק את כתובות הארנק שלך.\n\n"
        "כדי לעדכן כתובות:\n"
        "`/set_bnb <כתובת_BNB>`\n"
        "`/set_ton <כתובת_TON>`\n\n"
        f"האזור האישי שלך באתר:\n{hub_url}\n\n"
        "שם יוצגו כתובותיך, קישורים לחוזה SLH בביננס, ו־QR לשיתוף הכרטיס שלך.\n\n"
        "_שימו לב: העברות SLH ו‑BNB מתבצעות בארנק החיצוני שלכם (MetaMask/Tonkeeper וכד'), "
        "המערכת רק עוזרת לסנכרן ולשתף את הפרטים בקהילה._"
    )

    await update.effective_chat.send_message(text, parse_mode="Markdown")


async def cmd_set_bnb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not user:
        return

    if not context.args:
        await update.effective_chat.send_message("שימוש: /set_bnb <כתובת_BNB>")
        return

    address = context.args[0].strip()
    if not address.startswith("0x") or len(address) < 30:
        await update.effective_chat.send_message("הכתובת לא נראית כמו כתובת BNB תקינה.")
        return

    from .db import SessionLocal

    db = SessionLocal()
    try:
        wallet = await _ensure_wallet_record(user, db)
        wallet.bnb_address = address
        db.commit()
    finally:
        db.close()

    await update.effective_chat.send_message("✅ כתובת ה‑BNB שלך נשמרה בהצלחה.")


async def cmd_set_ton(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not user:
        return

    if not context.args:
        await update.effective_chat.send_message("שימוש: /set_ton <כתובת_TON>")
        return

    address = " ".join(context.args).strip()

    from .db import SessionLocal

    db = SessionLocal()
    try:
        wallet = await _ensure_wallet_record(user, db)
        wallet.ton_address = address
        db.commit()
    finally:
        db.close()

    await update.effective_chat.send_message("✅ כתובת ה‑TON שלך נשמרה בהצלחה.")


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = (
        "ℹ️ *מערכת הארנק הקהילתי של SLH*\n\n"
        "1️⃣ תרשום את כתובת ה‑BNB שלך עם:/set_bnb\n"
        "2️⃣ תרשום את כתובת ה‑TON שלך עם:/set_ton\n"
        "3️⃣ קבל קישור לכרטיס האישי שלך עם:/wallet\n\n"
        "העברות SLH נעשות דרך הארנק שלך על חוזה ה‑SLH ברשת BNB:\n"
        f"`{settings.slh_token_address}`\n\n"
        "מי שיש לו BNB יכול להחליף / לשלוח SLH בין חברי הקהילה באופן חופשי.\n"
        "מי שאין לו – יקבל הסבר ורשימת ספקים חיצוניים לרכישת BNB/קריפטו (להוסיף בהמשך)."
    )

    await update.effective_chat.send_message(text, parse_mode="Markdown")


@router.post("/telegram/webhook")
async def telegram_webhook(
    request: Request,
    db: Session = Depends(get_db),  # reserved for future use
) -> dict:
    body = await request.body()
    if not body:
        raise HTTPException(status_code=400, detail="Empty body")

    try:
        data = json.loads(body.decode("utf-8"))
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    app = await get_application()
    update = Update.de_json(data, app.bot)
    await app.process_update(update)

    return {"ok": True}
