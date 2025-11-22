import os


TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
API_BASE_URL = os.getenv("API_BASE_URL", "").rstrip("/")  # e.g. https://web-production-XXXX.up.railway.app

if not TELEGRAM_BOT_TOKEN:
    raise RuntimeError("TELEGRAM_BOT_TOKEN is required for bot-service")
if not API_BASE_URL:
    raise RuntimeError("API_BASE_URL is required for bot-service")
