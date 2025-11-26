import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import wallet as wallet_router
from app import telegram  # מכאן מגיע ה-webhook של הטלגרם

# =========================
#  Logging בסיסי
# =========================

log_level = getattr(settings, "LOG_LEVEL", "info").upper()
logging.basicConfig(level=log_level)
logger = logging.getLogger(__name__)

# =========================
#  FastAPI app
# =========================

app = FastAPI(
    title="SLH Community Wallet API",
    version="0.1.0",
)

# CORS פתוח – אפשר להקשיח בהמשך
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
    Endpoint לריילווי – אם זה מחזיר 200 OK, ה-service נחשב 'חי'.
    """
    return {"status": "ok"}


@app.get("/")
async def root():
    """
    Root פשוט – נוח לבדיקה מהדפדפן.
    """
    return {
        "service": "slh_community_wallet",
        "status": "ok",
        "env": getattr(settings, "ENV", "unknown"),
    }


# =========================
#  Routers
# =========================

# API של הארנק (BSC + פנימי)
app.include_router(wallet_router.router)

# API של הבוט (webhook /telegram/webhook וכו')
app.include_router(telegram.router)


# =========================
#  Events
# =========================

@app.on_event("startup")
async def on_startup():
    logger.info("🚀 SLH Community Wallet API started")


@app.on_event("shutdown")
async def on_shutdown():
    logger.info("👋 SLH Community Wallet API shutdown")
