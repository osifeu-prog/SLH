# Bot settings (env backed)
import os
from dotenv import load_dotenv
load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
SLH_API_BASE = os.getenv("SLH_API_BASE", "https://slhapi-bot.up.railway.app")
ADMIN_CHAT_IDS = [i for i in os.getenv("ADMIN_CHAT_IDS", "").split(",") if i]
TZ = os.getenv("TZ", "UTC")
PERSIST_FILE = os.getenv("PERSIST_FILE", "data/users.json")
SHOW_ALWAYS_MENU = True  # keep main menu persistent
