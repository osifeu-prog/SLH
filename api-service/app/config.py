import os


class Settings:
    """Simple settings reader from environment variables."""

    ENV: str = os.getenv("ENV", "production")
    BASE_URL: str = os.getenv("BASE_URL", "").rstrip("/")
    FRONTEND_API_BASE: str = os.getenv("FRONTEND_API_BASE", "").rstrip("/")

    DATABASE_URL: str = os.getenv("DATABASE_URL", "")
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    # Blockchain / SLH specific
    SLH_TOKEN_ADDRESS: str = os.getenv("SLH_TOKEN_ADDRESS", "0xACb0A09414CEA1C879c67bB7A877E4e19480f022")
    BSC_RPC_URL: str = os.getenv("BSC_RPC_URL", "https://bsc-dataseed.binance.org/")
    BSCSCAN_API_KEY: str | None = os.getenv("BSCSCAN_API_KEY")
    SLH_TON_FACTOR: int = int(os.getenv("SLH_TON_FACTOR", "1000"))

    SECRET_KEY: str = os.getenv("SECRET_KEY", "insecure-dev-key")


settings = Settings()
