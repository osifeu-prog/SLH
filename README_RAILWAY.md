# SLH Community Wallet – Railway Setup

פרויקט זה הוא ארנק קהילתי פשוט ל-SLH על רשת BNB, עם בוט טלגרם ו-API באותו שירות.

## 1. מבנה הפרויקט

```
SLH/
  app/
    __init__.py
    config.py
    db.py
    models.py
    schemas.py
    main.py
    telegram_webhook.py
    routers/
      __init__.py
      wallet.py
  requirements.txt
  Procfile
  README_RAILWAY.md
```

## 2. פריסת השירות על Railway

1. חבר את ריפו ה-GitHub שבו נמצא הפרויקט לשירות חדש מסוג **Web**.
2. ב-*Settings → Deploy* ודא שהפקודת ההפעלה היא:

   ```bash
   uvicorn app.main:app --host 0.0.0.0 --port 8000
   ```

3. ב-*Variables* הגדר:

   - `DATABASE_URL` – מכתובת החיבור של שירות ה-Postgres (בריילווי). לדוגמה:  
     `postgresql+psycopg2://USER:PASSWORD@postgres.railway.internal:5432/railway`
   - `TELEGRAM_BOT_TOKEN` – הטוקן של הבוט.
   - `BASE_URL` – ה-URL הציבורי של השירות, למשל:  
     `https://web-production-XXXX.up.railway.app`
   - `COMMUNITY_LINK` – קישור לקבוצת הטלגרם של הקהילה (אופציונלי).

4. ודא ששירות ה-Postgres מחובר לאותו Environment (production).

5. פרוס (Deploy) את השירות ובדוק בדפדפן:

   - `GET /health` → אמור להחזיר `{"status": "ok"}`.

## 3. חיבור הבוט (Webhook)

אחרי שהשירות רץ ועולה בכתובת הציבורית, קבע את ה-Webhook של טלגרם:

```bash
https://api.telegram.org/bot<TELEGRAM_BOT_TOKEN>/setWebhook?url=https://web-production-XXXX.up.railway.app/telegram/webhook
```

החלף את `<TELEGRAM_BOT_TOKEN>` וה-URL לדומיין האמיתי שלך.

אם אי פעם תעבור לפולינג ותבטל Webhook:

```bash
https://api.telegram.org/bot<TELEGRAM_BOT_TOKEN>/deleteWebhook
```

## 4. זרימת שימוש בבוט

1. המשתמש כותב לבוט `/start` → מקבל הודעת פתיחה ופקודות זמינות.
2. `/wallet` → הסבר קצר איך להגדיר ארנק.
3. `/set_wallet 0xBNB 0xSLH` → שמירת כתובת BNB וכתובת SLH בבסיס הנתונים.
4. `/balances` → הצגת הכתובות השמורות עבור המשתמש.

כל הנתונים נשמרים בטבלת `wallets` ב-Postgres.

## 5. בדיקות מהירות אחרי פריסה

1. בדפדפן/ב-Postman:
   - `GET https://web-production-XXXX.up.railway.app/health`
   - `GET https://web-production-XXXX.up.railway.app/api/wallet/by-telegram/123` (אם כבר קיים ארנק)

2. בצד הבוט:
   - שלח `/start` → אמור לקבל תשובה.
   - שלח `/set_wallet ...` → אמור לקבל ✅.
   - שלח `/balances` → אמורה להופיע הודעה עם הכתובות.

אם משהו לא עובד:

- בדוק את *HTTP Logs* של שירות ה-Web בריילווי.
- ודא שה-`TELEGRAM_BOT_TOKEN` נכון.
- ודא שה-`DATABASE_URL` מצביע על שירות ה-Postgres הפעיל.
