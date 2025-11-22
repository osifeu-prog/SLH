import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .db import init_db
from .routers import wallet as wallet_router
from .telegram_bot import router as telegram_router


# ---------------------------------------------------
# Logging
# ---------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)


# ---------------------------------------------------
# FastAPI App
# ---------------------------------------------------
app = FastAPI(
    title="SLH Community Wallet",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)


# ---------------------------------------------------
# CORS
# ---------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------
# Startup
# ---------------------------------------------------
@app.on_event("startup")
def on_startup():
    """
    יצירת טבלאות רק אם אין Alembic.
    אם תפעיל Alembic – init_db לא מפריע.
    """
    init_db()
    logging.info("Database initialized.")


# ---------------------------------------------------
# Health
# ---------------------------------------------------
@app.get("/health")
async def health():
    return {"status": "ok"}


# ---------------------------------------------------
# Routers
# ---------------------------------------------------
app.include_router(wallet_router.router)
app.include_router(telegram_router)
