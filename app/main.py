import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .db import Base, engine
from .routers import wallet as wallet_router
from . import telegram  # זה הקובץ app/telegram.py החדש

logger = logging.getLogger("slh")

app = FastAPI(
    title="SLH Community Wallet",
    version="0.1.0",
)

# יצירת טבלאות DB (אם צריך)
Base.metadata.create_all(bind=engine)

# CORS בסיסי (שיהיה נחמד ל-frontend)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(wallet_router.router)
app.include_router(telegram.router)


@app.get("/")
async def index():
    return {
        "ok": True,
        "service": "SLH Community Wallet",
        "env": settings.env,
    }
