import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings

# =========================
#  Logging
# =========================

log_level = getattr(settings, "LOG_LEVEL", "info").upper()
logging.basicConfig(level=log_level)
logger = logging.getLogger(__name__)

# =========================
#  FastAPI app
# =========================

app = FastAPI(
    title="SLH Community Wallet API",
    version="0.2.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =========================
#  Health & Root
# =========================

@app.get("/health")
async def health():
    """
    Railway healthcheck.
    אם זה מחזיר 200 – ה-service נחשב חי.
    """
    return {"status": "ok"}


@app.get("/")
async def root():
    return {
        "service": "slh_community_wallet",
        "status": "ok",
        "env": getattr(settings, "ENV", "unknown"),
    }

# =========================
#  Routers – נטען בזהירות
# =========================

# Wallet API
try:
    from app.routers import wallet as wallet_router
    app.include_router(wallet_router.router)
    logger.info("✅ Wallet router loaded")
except Exception as e:
    logger.exception("❌ Failed to init wallet router: %s", e)

# Telegram Bot webhook
try:
    from app import telegram
    app.include_router(telegram.router)
    logger.info("✅ Telegram router loaded")
except Exception as e:
    logger.exception("❌ Failed to init telegram router: %s", e)

# =========================
#  Events
# =========================

@app.on_event("startup")
async def on_startup():
    logger.info("🚀 SLH Community Wallet API started")


@app.on_event("shutdown")
async def on_shutdown():
    logger.info("👋 SLH Community Wallet API shutdown")
