
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .db import Base, engine
from .routers import wallet as wallet_router
from . import telegram_http

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("slh")

settings = get_settings()

# Create DB schema if needed
logger.info("Initializing database...")
Base.metadata.create_all(bind=engine)
logger.info("Database initialized.")

tags_metadata = [
    {
        "name": "wallet",
        "description": "Manage SLH community wallets (BNB/SLH + TON).",
    },
    {
        "name": "telegram",
        "description": "Telegram webhook for the SLH community bot.",
    },
]

app = FastAPI(
    title=settings.PROJECT_NAME,
    version="0.1.0",
    openapi_tags=tags_metadata,
)

# CORS for future frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)

@app.get("/", tags=["default"])
def index():
    return {
        "ok": True,
        "service": settings.PROJECT_NAME,
        "env": settings.ENV,
    }

# Routers
app.include_router(wallet_router.router)
app.include_router(telegram_http.router)
