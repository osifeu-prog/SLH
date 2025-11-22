# SLH Community Wallet – BNB + Telegram

גרסה מצומצמת ונקייה של ארנק קהילתי ל‑SLH על רשת BNB,
עם חיבור לבוט טלגרם ולדפי HTML אישיים לכל משתמש.

## 1. מה המערכת עושה?

* מזהה משתמשים לפי **Telegram ID** בלבד – בלי סיסמאות.
* שומרת עבורם:
  * כתובת BNB (ל‑SLH על Binance Smart Chain)
  * כתובת TON (אופציונלי, להמשך חלוקה ב‑TON)
* מייצרת כרטיס אישי באתר: `/u/{telegram_id}`
  * מציג כתובת BNB
  * מציג כתובת TON
  * מציג את חוזה ה‑SLH ברשת BNB:
    * 0xACb0A09414CEA1C879c67bB7A877E4e19480f022
* הבוט בטלגרם מעדכן את הנתונים בבסיס הנתונים בלבד.
  ההעברות בפועל מתבצעות בארנקים החיצוניים של המשתמשים.

---

## 2. מבנה הפרויקט

```text
SLH_CommunityWallet/
  app/
    __init__.py
    main.py
    config.py
    db.py
    models.py
    telegram_bot.py
    routers/
      __init__.py
      wallet.py
    templates/
      base.html
      index.html
      user_card.html
  requirements.txt
  Procfile
  runtime.txt
  README.md
```

---

## 3. משתני סביבה (ENV) – Koyeb / מקומי

חובה להגדיר:

```bash
DATABASE_URL=postgresql://USER:PASSWORD@HOST:PORT/DBNAME?sslmode=require
TELEGRAM_BOT_TOKEN=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
BASE_URL=https://thin-charlot-osifungar-d382d3c9.koyeb.app
SLH_TOKEN_ADDRESS=0xACb0A09414CEA1C879c67bB7A877E4e19480f022
```

* DATABASE_URL – ממשיך להשתמש ב‑Neon PostgreSQL שכבר פתחת.
* BASE_URL – ה‑URL של השירות על Koyeb (כבר קיים אצלך).
* SLH_TOKEN_ADDRESS – כבר תואם לחוזה שהגדרת.

אפשר להוסיף קובץ `.env` מקומי לצורך פיתוח:

```env
DATABASE_URL=postgresql://...
TELEGRAM_BOT_TOKEN=...
BASE_URL=http://localhost:8000
SLH_TOKEN_ADDRESS=0xACb0A09414CEA1C879c67bB7A877E4e19480f022
```

---

## 4. DB Schema – Neon

טבלה אחת פשוטה: `wallets`

```sql
CREATE TABLE IF NOT EXISTS wallets (
    telegram_id      VARCHAR(32) PRIMARY KEY,
    username         VARCHAR(255),
    first_name       VARCHAR(255),
    last_name        VARCHAR(255),
    bnb_address      VARCHAR(64),
    ton_address      VARCHAR(128),
    created_at       TIMESTAMPTZ DEFAULT NOW(),
    updated_at       TIMESTAMPTZ DEFAULT NOW()
);
```

אפשר להריץ את זה פעם אחת ב‑Neon (או לתת ל‑SQLAlchemy ליצור אוטומטית – זה כבר מוגדר ב־`init_db()`).

---

## 5. זרימת משתמש – BOT

1. המשתמש שולח `/start` לבוט
   * מקבל הסבר קצר על הארנק והחוזה.

2. המשתמש שולח `/wallet`
   * נוצרת (אם צריך) רשומת `wallets` עבור ה‑Telegram ID שלו.
   * הבוט מחזיר קישור:
     * `{BASE_URL}/u/{telegram_id}`

3. המשתמש שולח:

   ```text
   /set_bnb 0x....
   ```

   * נשמרת `bnb_address` בבסיס הנתונים.

4. המשתמש שולח:

   ```text
   /set_ton EQB....
   ```

   * נשמרת `ton_address` בבסיס הנתונים.

5. דרך הדפדפן:

   * `/u/224223270` – מציג כרטיס אישי למשתמש:
     * פרטי טלגרם (id, username)
     * כתובת BNB + קישור ל‑BscScan
     * כתובת TON (אם קיימת)
     * קישור לשיתוף הכרטיס.

---

## 6. הפעלה מקומית

```bash
cd SLH_CommunityWallet
python -m venv .venv
source .venv/bin/activate  # ב־Windows: .venv\Scripts\activate
pip install -r requirements.txt

# קובץ .env עם DATABASE_URL + TELEGRAM_BOT_TOKEN + BASE_URL
uvicorn app.main:app --reload --port 8000
```

ואז:

* פותחים דפדפן: `http://localhost:8000/`
* מגדירים webhook לבוט (פעם אחת), דרך ה‑API של טלגרם:

  ```bash
  curl -X POST "https://api.telegram.org/bot<TELEGRAM_BOT_TOKEN>/setWebhook" \
    -d "url=http://localhost:8000/telegram/webhook"
  ```

(ב‑Koyeb זה יהיה ה‑BASE_URL שלך במקום `localhost:8000`.)

---

## 7. פריסה ל‑Koyeb

1. דוחפים את התיקייה הזו ל‑GitHub (לריפו `SLH_Wallet` או חדש).
2. ב‑Koyeb מגדירים:
   * Source: GitHub → הריפו החדש
   * Buildpack
   * Port: `8000`
3. מגדירים Environment:

   ```text
   DATABASE_URL=... (Neon)
   TELEGRAM_BOT_TOKEN=...
   BASE_URL=https://thin-charlot-osifungar-d382d3c9.koyeb.app
   SLH_TOKEN_ADDRESS=0xACb0A09414CEA1C879c67bB7A877E4e19480f022
   ```

4. לאחר שהשירות עולה:

   ```bash
   curl -X POST "https://api.telegram.org/bot<TELEGRAM_BOT_TOKEN>/setWebhook" \
     -d "url=https://thin-charlot-osifungar-d382d3c9.koyeb.app/telegram/webhook"
   ```

5. בודקים:
   * `/health` – אמור להחזיר `{"status": "ok"}`
   * `/` – דף נחיתה של SLH Wallet
   * `/u/<telegram_id>` – כרטיס משתמש (אחרי ששלחת /wallet + /set_bnb בבוט)

---

## 8. לאן ממשיכים מכאן?

* אפשר להוסיף:
  * סטייקינג (טבלאות נוספות, מודל תשואה חודשי 10%)
  * לוגיקת P2P פנימית (internal ledger)
  * Dashboard לאדמין (דוחות, יצוא CSV)
  * חישוב אוטומטי של יתרות דרך BscScan / TON API
  * יצירת QR אמיתי בצד ה‑frontend.

בשלב זה יש לך בסיס נקי:

* בוט טלגרם פשוט
* DB אחד ברור
* תבניות HTML בסיסיות
* פריסה שצריכה לעבוד על Koyeb עם Neon.

מכאן אפשר רק להוסיף שכבות ותכונות – בלי לסבך את היסודות.
