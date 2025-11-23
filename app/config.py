import os
import json
from functools import lru_cache
from typing import List, Optional


class Settings:
    # ============================
    #   META / ENVIRONMENT
    # ============================
    PROJECT_NAME: str = "SLH Community Wallet"
    ENV: str = os.getenv("ENV", "development")
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    # ============================
    #   DATABASE
    # ============================
    DATABASE_URL: str = os.getenv("DATABASE_URL", "")

    # ============================
    #   TELEGRAM / BOT CONFIG
    # ============================
    TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    BOT_USERNAME: str = os.getenv("BOT_USERNAME", "")
    ADMIN_LOG_CHAT_ID: str = os.getenv("ADMIN_LOG_CHAT_ID", "")

    # Webhook base URL:
    BASE_URL: str = os.getenv("BASE_URL", "").rstrip("/")

    # ============================
    #   PUBLIC FRONTEND REFERENCES
    # ============================
    FRONTEND_API_BASE: str = os.getenv("FRONTEND_API_BASE", "")
    FRONTEND_BOT_URL: str = os.getenv("FRONTEND_BOT_URL", "")
    COMMUNITY_LINK: str = os.getenv("COMMUNITY_LINK", "")

    # ============================
    #   ON-CHAIN SLH / BSC CONFIG
    # ============================
    BSC_RPC_URL: str = os.getenv("BSC_RPC_URL", "")
    BSCSCAN_API_KEY: str = os.getenv("BSCSCAN_API_KEY", "")
    SLH_TOKEN_ADDRESS: str = os.getenv("SLH_TOKEN_ADDRESS", "")
    SLH_TOKEN_DECIMALS: int = int(os.getenv("SLH_TOKEN_DECIMALS", "18"))
    SLH_TON_FACTOR: int = int(os.getenv("SLH_TON_FACTOR", "1000"))

    # GLOBAL API BASE
    API_BASE_URL: str = os.getenv("API_BASE_URL", "")

    # ============================
    #   PAYMENT METHODS
    # ============================
    PAYMENT_METHODS_RAW: str = os.getenv(
        "PAYMENT_METHODS",
        '["BNB","SLH","CREDIT_CARD","BANK_TRANSFER"]'
    )

    @property
    def PAYMENT_METHODS(self) -> List[str]:
        """Parses the PAYMENT_METHODS JSON, with fallback."""
        try:
            return json.loads(self.PAYMENT_METHODS_RAW)
        except Exception:
            return [self.PAYMENT_METHODS_RAW]

    # ============================
    #   COMPATIBILITY LAYER
    # ============================

    @property
    def env(self) -> str:
        """Compatibility for code expecting settings.env."""
        return self.ENV

    @property
    def telegram_bot_token(self) -> str:
        """Compatibility for code expecting settings.telegram_bot_token."""
        return self.TELEGRAM_BOT_TOKEN

    @property
    def bot_username(self) -> str:
        return self.BOT_USERNAME

    @property
    def base_url(self) -> str:
        return self.BASE_URL


@lru_cache
def get_settings() -> "Settings":
    return Settings()


# This is imported everywhere across the app:
# from app.config import settings
settings = get_settings()
