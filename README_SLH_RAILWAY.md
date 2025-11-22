# SLH Community Wallet – Railway Monolith

תשתית בסיסית לבוט + API לארנק קהילתי של SLH, רצה כשירות אחד ב-Railway.

## מבנה

- `app/` – קוד FastAPI + בוט טלגרם
  - `config.py` – קריאת משתני סביבה
  - `db.py` – SQLAlchemy + init_db
  - `models.py` – מודל Wallet
  - `schemas.py` – סכמות Pydantic
  - `routers/wallet.py` – REST API לניהול ארנקים
  - `telegram_bot.py` – פקודות /start /wallet /set_wallet /balances + webhook
  - `main.py` – יצירת FastAPI, CORS, startup
- `requirements.txt`
- `alembic/`, `alembic.ini` – שלד למיגרציות (אופציונלי)

## משתני סביבה חשובים (Railway)

- `DATABASE_URL` – מחרוזת חיבור לפוסטגרז של Railway (כבר יש לך שירות Postgres).
- `TELEGRAM_BOT_TOKEN` – הטוקן של הבוט.
- `BASE_URL` – ה-URL החיצוני של השירות, למשל:
  - `https://web-production-481a.up.railway.app`
- `LOG_LEVEL` – למשל `INFO`.

שאר המשתנים (BSCSCAN וכו') לא משמשים בקוד הזה כרגע, אפשר להשאיר לעתיד.

## פקודות בוט

- `/start` – מסך פתיחה.
- `/wallet` – הסבר ורמז לפקודת /set_wallet.
- `/set_wallet <BNB> <SLH>` – שומר/מעדכן רשומת ארנק בטבלה `wallets`.
- `/balances` – מביא את הכתובות + יתרות דמו (0) מ-API.

## בדיקות לאחר פריסה

1. ודא שהשירות `web` ב-Railway ירוק והלוג מכיל:
   - `Database initialized.`
   - `Startup complete – DB + Telegram bot ready.`

2. קבע webhook (אם לא נקבע כבר):

   ```text
   https://api.telegram.org/bot<TELEGRAM_BOT_TOKEN>/setWebhook?url=https://web-production-481a.up.railway.app/telegram/webhook
   ```

3. בבוט:
   - שלח `/start` – אמור להחזיר הודעת ברוך הבא.
   - שלח `/wallet`.
   - שלח `/set_wallet 0xd0617b54fb4b6b66307846f217b4d685800e3da4 0xACb0A09414CEA1C879c67bB7A877E4e19480f022`
   - אמור לקבל `✅ הארנק שלך עודכן בהצלחה במערכת SLH.`
   - שלח `/balances` – תראה את הכתובות ויתרות 0.

4. בדיקת API בדפדפן:
   - פתח `https://web-production-481a.up.railway.app/docs`
   - נסה `GET /api/wallet/{telegram_id}` עם ה-ID שלך.
   - נסה `GET /api/wallet/{telegram_id}/balances`.

## Alembic (לא חובה כרגע)

אם תרצה, תוכל להריץ מיגרציה ראשונית:

```bash
alembic revision -m "init wallets" --autogenerate
alembic upgrade head
```

זה ישתמש ב-`Base.metadata` מהקוד.