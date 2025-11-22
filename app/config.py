from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    database_url: str = Field(..., alias="DATABASE_URL")
    telegram_bot_token: str = Field(..., alias="TELEGRAM_BOT_TOKEN")
    base_url: str = Field("http://localhost:8000", alias="BASE_URL")
    slh_token_address: str = Field(
        "0xACb0A09414CEA1C879c67bB7A877E4e19480f022", alias="SLH_TOKEN_ADDRESS"
    )

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
