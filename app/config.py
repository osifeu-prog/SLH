from pydantic_settings import BaseSettings
from pydantic import AnyUrl
from functools import lru_cache


class Settings(BaseSettings):
    env: str = "production"
    log_level: str = "INFO"

    database_url: AnyUrl
    telegram_bot_token: str

    base_url: str | None = None
    frontend_api_base: str | None = None
    community_link: str | None = None

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()