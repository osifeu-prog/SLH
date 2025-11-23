import os
from functools import lru_cache


class Settings:
    PROJECT_NAME: str = "SLH Community Wallet"
    ENV: str = os.getenv("ENV", "development")

    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL", "")

    # Telegram / bot
    TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    BOT_USERNAME: str = os.getenv("BOT_USERNAME", "")
    BASE_URL: str = os.getenv("BASE_URL", "").rstrip("/")

    # Other
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    # כדי ש-main.py יוכל להשתמש settings.env
    @property
    def env(self) -> str:
        return self.ENV


@lru_cache
def get_settings() -> "Settings":
    return Settings()


# זה מה ש-main.py מצפה לו:
# from .config import settings
settings = get_settings()
