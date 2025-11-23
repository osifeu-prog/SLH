import os
from pydantic import BaseModel


class Settings(BaseModel):
    env: str = os.getenv("ENV", "production")
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./slh_wallet.db")
    telegram_bot_token: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    base_url: str = os.getenv("BASE_URL", "")  # e.g. https://web-production-xxxx.up.railway.app
    log_level: str = os.getenv("LOG_LEVEL", "INFO")
    admin_log_chat_id: str | None = os.getenv("ADMIN_LOG_CHAT_ID")


settings = Settings()
