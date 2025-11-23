import logging
import os

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .db import init_db
from .telegram import router as telegram_router
from .wallet import router as wallet_router

logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO))
logger = logging.getLogger("slh")

app = FastAPI(
    title="SLH Community Wallet",
    version="0.1.0",
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def on_startup():
    logger.info("Initializing database...")
    init_db()
    logger.info("Database initialized.")

    # ניסיון להגדיר Webhook לטלגרם אם יש לנו BASE_URL + TELEGRAM_BOT_TOKEN
    if settings.telegram_bot_token and settings.base_url:
        webhook_url = settings.base_url.rstrip("/") + "/telegram/webhook"
        logger.info("Setting Telegram webhook to %s", webhook_url)
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(
                    f"https://api.telegram.org/bot{settings.telegram_bot_token}/setWebhook",
                    json={"url": webhook_url},
                )
            logger.info("Telegram setWebhook response: %s", resp.text)
        except Exception as e:
            logger.error("Failed to set Telegram webhook: %s", e)


@app.get("/")
async def index():
    return {
        "ok": True,
        "service": "SLH Community Wallet",
        "env": settings.env,
    }


# Routers
app.include_router(wallet_router)
app.include_router(telegram_router)
