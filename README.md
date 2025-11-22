# SLH Community Wallet – Monorepo (API + Bot + Frontend)

זהו שלד פרויקט מלא ל-SLH Wallet:

- `api-service/` – FastAPI + PostgreSQL – אחראי על:
  - רישום ארנקים לפי Telegram ID
  - לוגיקת Ledger פנימית (SLH בין משתמשים)
  - נקודות API שהבוט וה-Frontend משתמשים בהן

- `bot-service/` – בוט טלגרם (python-telegram-bot, polling)
  - רישום/עדכון כתובות BNB/SLH דרך פקודות
  - שליפת יתרות דרך ה-API

- `web-frontend/` – Next.js קליל
  - דף נחיתה
  - בדיקת ארנק לפי Telegram ID

## הרצה על Railway (המלצה בסיסית)

### 1. שירות Postgres

צור Service מסוג Postgres בריילווי וקבל את ה-`DATABASE_URL`.

### 2. שירות API (`web` / `api-service`)

1. צור Service חדש מ-GitHub ובחר את הריפו הזה.
2. ב-Settings של השירות:
   - Root Directory: `api-service`
   - Build command: `pip install -r requirements.txt`
   - Start command: `uvicorn app.main:app --host 0.0.0.0 --port 8000`
3. Variables:
   - `DATABASE_URL` – מהשירות Postgres (דרך בחירת "Connect to Database")
   - `ENV=production`
   - `LOG_LEVEL=INFO`
   - `BASE_URL=https://<your-api-subdomain>.up.railway.app`
   - `FRONTEND_API_BASE` – אותו דבר כמו BASE_URL
   - `SLH_TOKEN_ADDRESS=0xACb0A09414CEA1C879c67bB7A877E4e19480f022`
   - `BSC_RPC_URL=https://bsc-dataseed.binance.org/`
   - `SLH_TON_FACTOR=1000`
   - `SECRET_KEY` – מחרוזת אקראית

4. (אופציונלי אך מומלץ) – הרצת Alembic:
   - התחבר ל-`web` ב-Railway דרך Web Console או shell
   - הרץ:
     - `cd api-service`
     - `alembic upgrade head`

### 3. שירות Bot (`bot-service`)

1. צור Service חדש מאותו ריפו.
2. Root Directory: `bot-service`
3. Build command: `pip install -r requirements.txt`
4. Start command: `python -m bot.main`
5. Variables:
   - `TELEGRAM_BOT_TOKEN=...` – מה-BotFather
   - `API_BASE_URL=https://<your-api-subdomain>.up.railway.app` (אותו של ה-API)

> חשוב: עבור עבודה במצב polling אין צורך ב-webhook. ודא שה-webhook מבוטל:> `https://api.telegram.org/bot<TELEGRAM_BOT_TOKEN>/deleteWebhook`

### 4. שירות Frontend (`web-frontend`)

1. צור Service חדש מאותו ריפו.
2. Root Directory: `web-frontend`
3. Build: `npm install && npm run build`
4. Start: `npm start`
5. Variables:
   - `NEXT_PUBLIC_API_BASE=https://<your-api-subdomain>.up.railway.app`

## שימוש בסיסי בבוט (אחרי שהכל רץ)

- `/start` – קבלת הסבר קצר.
- `/wallet` – קבלת הסבר על רישום ארנק.
- `/set_wallet <BNB> [SLH]` – רישום כתובות (אם SLH חסר – משתמש בכתובת BNB).
- `/balances` – שליפת יתרות בסיסית (כרגע מחזיר 0 – לשדרוג עתידי).

## הערות המשך

- כעת יש שלד נקי וברור שאפשר לפתח ממנו:
  - הוספת סטייקינג (`/api/staking/...`)
  - הוספת מסחר P2P (`/api/trade/...`)
  - הרחבת ה-Frontend לעמוד פרופיל מלא, סטטוס סטייקינג וכו'.
