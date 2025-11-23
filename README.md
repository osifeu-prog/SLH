# SLH Community Wallet (web + Telegram webhook)

שירות FastAPI פשוט שמנהל ארנקי קהילה (BNB/SLH + TON) ומתחבר לבוט טלגרם.

## מבנה

- `app/main.py` — אפליקציית FastAPI, CORS, סטארטאפ, הגדרת Webhook לטלגרם
- `app/models.py` — מודל SQLAlchemy לטבלת `wallets`
- `app/db.py` — יצירת engine + Session + `init_db`
- `app/schemas.py` — מודלי Pydantic ל-API
- `app/wallet.py` — מסלולי API לניהול ארנקים + פונקציית `upsert_wallet`
- `app/telegram.py` — מסלול `/telegram/webhook` שמקבל עדכוני טלגרם ומטפל בפקודות
- `requirements.txt` — חבילות פייתון
- `Dockerfile` — להרצה ב-Railway / Docker

## משתני סביבה חשובים

ב-Railway, בשירות `web`:

- `DATABASE_URL` — URL של PostgreSQL שריילווי נותן
- `TELEGRAM_BOT_TOKEN` — טוקן של הבוט (SLH משקיעים)
- `BASE_URL` — ה-URL של השירות, לדוגמה: `https://web-production-XXXX.up.railway.app`
- `ENV` — אופציונלי, לדוגמה: `production`
- `LOG_LEVEL` — `INFO` / `DEBUG` וכו'
- `ADMIN_LOG_CHAT_ID` — אופציונלי, לא בשימוש כרגע

## מסלולי API

- `GET /` — בדיקת חיים
- `POST /api/wallet/set` — יצירה/עדכון ארנק
- `GET /api/wallet/{telegram_id}` — שליפת ארנק
- `GET /api/wallet/{telegram_id}/balances` — יתרות (כרגע 0, placeholder)
- `POST /telegram/webhook` — Webhook של טלגרם

## פקודות בטלגרם

- `/start` — מסך ברוך הבא
- `/wallet` — הסבר על רישום ארנק
- `/set_wallet <BNB> [TON]` — שמירת כתובת ארנק
- `/balances` — הצגת נתוני הארנק השמורים במערכת

## פריסה לריילווי (Railway)

1. ארוז את התיקייה הזו ל-ZIP והעלה לריפו ב-GitHub או ישירות ל-Railway.
2. ודא שבשירות `web` ב-Railway:
   - מוגדרים משתני הסביבה הנ"ל.
   - מחובר ה-Postgres דרך `DATABASE_URL`.
3. Railway יבנה לפי `Dockerfile` ויריץ את `uvicorn` על הפורט שהוגדר.

לאחר שהשירות פעיל:

- פתח `https://YOUR_WEB_URL/` ותראה:
  `{ "ok": true, "service": "SLH Community Wallet", "env": "production" }`
- פתח `https://YOUR_WEB_URL/docs` כדי לבדוק את ה-API.
- שלח `/start` לבוט בטלגרם — הוא ישתמש ב-webhook החדש.
