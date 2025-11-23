import logging

from fastapi import FastAPI

from .config import settings
from .db import init_db
from .routers import wallet as wallet_router
from . import telegram_webhook

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)

app = FastAPI(title="SLH Community Wallet", version="0.1.0")


@app.on_event("startup")
async def on_startup() -> None:
    init_db()
    logging.getLogger("slh.main").info(
        "Startup complete – DB ready, Telegram webhook endpoint mounted."
    )


app.include_router(wallet_router.router, prefix="/api/wallet", tags=["wallet"])
app.include_router(telegram_webhook.router, prefix="/telegram", tags=["telegram"])


@app.get("/")
async def index() -> dict:
    return {"message": "SLH Community Wallet API is running"}


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}
