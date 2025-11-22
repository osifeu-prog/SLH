import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .db import init_db
from .routers import wallet as wallet_router
from .telegram_bot import router as telegram_router, get_application

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)
logger = logging.getLogger("slh.main")

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

app.include_router(wallet_router.router)
app.include_router(telegram_router)


@app.on_event("startup")
async def on_startup() -> None:
    init_db()
    await get_application()
    logger.info("Startup complete – DB + Telegram bot ready.")


@app.get("/")
async def index() -> dict:
    return {
        "ok": True,
        "service": "SLH Community Wallet",
        "env": settings.env,
    }