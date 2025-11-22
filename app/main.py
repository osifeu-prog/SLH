import logging
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.db import init_db
from app.bot import get_application, handle_telegram_update
from app.routers.wallet import router as wallet_router

logger = logging.getLogger("slh.main")

app = FastAPI(title="SLH Community Wallet")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(wallet_router, prefix="/api/wallet")


@app.on_event("startup")
async def startup_event():
    logger.info("Initializing database...")
    init_db()

    logger.info("Initializing Telegram bot (webhook mode)...")
    bot_app = get_application()
    await bot_app.initialize()
    logger.info("Startup complete – DB + Telegram bot ready.")


@app.post("/telegram/webhook")
async def telegram_webhook(request: Request):
    data = await request.json()
    return await handle_telegram_update(data)


@app.get("/")
async def root():
    return {"service": "SLH Community Wallet", "status": "ok"}
