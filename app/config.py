import os
from pydantic.dataclasses import dataclass

@dataclass
class Settings:
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./slh.db")
    telegram_bot_token: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    base_url: str = os.getenv("BASE_URL", "http://localhost:8000")
    community_link: str | None = os.getenv("COMMUNITY_LINK")

settings = Settings()
