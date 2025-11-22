from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .db import Base, engine
from .routers import health, wallet, internal_transfer

logging.basicConfig(level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO))
logger = logging.getLogger("slh_wallet.api")

# Create all tables (for dev). In production, prefer Alembic migrations.
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="SLH Wallet API",
    version="0.2.0",
    description="Core API for SLH Community Wallet (BNB + TON + Internal Ledger).",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)

app.include_router(health.router)
app.include_router(wallet.router)
app.include_router(internal_transfer.router)


@app.get("/")
def index() -> dict:
    return {
        "name": "SLH Wallet API",
        "version": "0.2.0",
        "base_url": settings.BASE_URL or None,
    }
