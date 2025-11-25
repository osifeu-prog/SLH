import os

# 🔐 טוקן הבוט של טלגרם (SLH Community Wallet Bot)
TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")

# 🌐 בסיס ה-API של שרת הארנק (SLH Wallet API)
# דוגמה: https://slh-wallet-production.up.railway.app
API_BASE_URL: str = os.getenv("API_BASE_URL", "http://localhost:8000")

# 🌐 בסיס ה-API של מנוע TON Trading Bot Pro
# ברירת מחדל: השירות שרץ אצלך בריילווי
TON_API_BASE_URL: str = os.getenv(
    "TON_API_BASE_URL",
    "https://ton-production.up.railway.app",
)

# 🌍 כתובת אתר הפרויקט (GitHub Pages / Landing Page)
PROJECT_SITE_URL: str = os.getenv(
    "PROJECT_SITE_URL",
    "https://osifeu-prog.github.io/TON/",
)
