import asyncio
import logging
import os
from datetime import datetime
from decimal import Decimal
from types import SimpleNamespace
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app import models, schemas
from app.db import get_db

logger = logging.getLogger("slh.wallet")

router = APIRouter(prefix="/api/wallet", tags=["wallet"])

# --------- CONFIG ---------


def get_config() -> SimpleNamespace:
    """
    קורא משתני סביבה רלוונטיים ל-BSC/SLH.
    כל מה שהגדרת ב-Railway תחת web -> Variables.
    """
    return SimpleNamespace(
        BSC_RPC_URL=os.getenv(
            "BSC_RPC_URL", "https://bsc-dataseed.binance.org/"
        ),
        BSCSCAN_API_KEY=os.getenv("BSCSCAN_API_KEY"),
        SLH_TOKEN_ADDRESS=os.getenv("SLH_TOKEN_ADDRESS"),
        SLH_TOKEN_DECIMALS=int(os.getenv("SLH_TOKEN_DECIMALS") or "18"),
    )


config = get_config()

BSCSCAN_API_URL = "https://api.bscscan.com/api"

# --------- HELPERS: DB ---------


def upsert_wallet(
    db: Session,
    telegram_id: str,
    username: Optional[str],
    first_name: Optional[str],
    bnb_address: str,
    ton_address: Optional[str] = None,
) -> models.Wallet:
    """
    יוצר או מעדכן רשומת ארנק לפי telegram_id.
    slh_address = bnb_address (אותו ארנק ל-BNB ול-SLH).
    """
    wallet: Optional[models.Wallet] = db.get(models.Wallet, telegram_id)

    if wallet is None:
        wallet = models.Wallet(
            telegram_id=telegram_id,
            username=username,
            first_name=first_name,
            last_name=None,
            bnb_address=bnb_address,
            ton_address=ton_address,
            slh_address=bnb_address,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db.add(wallet)
        logger.info(
            "Created new wallet: telegram_id=%s bnb=%s ton=%s",
            telegram_id,
            bnb_address,
            ton_address,
        )
    else:
        wallet.username = username or wallet.username
        wallet.first_name = first_name or wallet.first_name
        wallet.bnb_address = bnb_address
        wallet.slh_address = bnb_address
        wallet.ton_address = ton_address or wallet.ton_address
        wallet.updated_at = datetime.utcnow()
        logger.info(
            "Updated wallet: telegram_id=%s bnb=%s ton=%s",
            telegram_id,
            bnb_address,
            ton_address,
        )

    db.commit()
    db.refresh(wallet)
    return wallet


# --------- HELPERS: BSC / BscScan ---------


async def _fetch_bnb_balance(address: str) -> Decimal:
    """
    מחזיר יתרת BNB אמיתית מ-BscScan (ביחידות BNB, לא wei).
    """
    if not config.BSCSCAN_API_KEY:
        logger.warning("BSCSCAN_API_KEY not configured – returning 0 BNB")
        return Decimal(0)

    params = {
        "module": "account",
        "action": "balance",
        "address": address,
        "apikey": config.BSCSCAN_API_KEY,
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(BSCSCAN_API_URL, params=params)
            resp.raise_for_status()
            data = resp.json()
    except Exception as exc:  # noqa: BLE001
        logger.exception("Failed to fetch BNB balance from BscScan: %s", exc)
        return Decimal(0)

    if data.get("status") != "1":
        logger.warning("BscScan BNB balance error: %s", data)
        return Decimal(0)

    wei_str = data.get("result", "0")
    try:
        wei = Decimal(wei_str)
    except Exception:  # noqa: BLE001
        logger.warning("Invalid wei value from BscScan: %s", wei_str)
        return Decimal(0)

    # 1 BNB = 1e18 wei
    return wei / Decimal("1e18")


async def _fetch_slh_balance(address: str) -> Decimal:
    """
    מחזיר יתרת טוקן SLH (BEP-20) לפי החוזה שסיפקת, דרך BscScan.
    משתמש ב-SLH_TOKEN_ADDRESS + SLH_TOKEN_DECIMALS מה-ENV.
    """
    if not config.BSCSCAN_API_KEY or not config.SLH_TOKEN_ADDRESS:
        logger.warning(
            "BSCSCAN_API_KEY or SLH_TOKEN_ADDRESS not configured – returning 0 SLH"
        )
        return Decimal(0)

    params = {
        "module": "account",
        "action": "tokenbalance",
        "contractaddress": config.SLH_TOKEN_ADDRESS,
        "address": address,
        "tag": "latest",
        "apikey": config.BSCSCAN_API_KEY,
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(BSCSCAN_API_URL, params=params)
            resp.raise_for_status()
            data = resp.json()
    except Exception as exc:  # noqa: BLE001
        logger.exception("Failed to fetch SLH balance from BscScan: %s", exc)
        return Decimal(0)

    # יש מצבים ש-BscScan מחזיר status="0" אבל עדיין נותן result; לא נכשיל את זה
    raw_str = data.get("result", "0")
    try:
        raw = Decimal(raw_str)
    except Exception:  # noqa: BLE001
        logger.warning("Invalid SLH raw balance value: %s", raw_str)
        return Decimal(0)

    decimals = int(os.getenv("SLH_TOKEN_DECIMALS") or config.SLH_TOKEN_DECIMALS or 18)
    factor = Decimal(10) ** Decimal(decimals)
    if factor == 0:
        return Decimal(0)

    return raw / factor


async def get_balances_live(wallet: models.Wallet) -> schemas.BalancesOut:
    """
    מחזיר BalancesOut עם נתונים חיים מ-BscScan.
    כרגע TON נשאר 0 / לא מחושב – אפשר להרחיב בהמשך.
    """
    if not wallet.bnb_address:
        return schemas.BalancesOut(
            telegram_id=wallet.telegram_id,
            bnb_address=None,
            ton_address=wallet.ton_address,
            slh_address=None,
            bnb_balance=0.0,
            slh_balance=0.0,
        )

    # BNB + SLH במקביל
    bnb_balance_dec, slh_balance_dec = await asyncio.gather(
        _fetch_bnb_balance(wallet.bnb_address),
        _fetch_slh_balance(wallet.bnb_address),
    )

    return schemas.BalancesOut(
        telegram_id=wallet.telegram_id,
        bnb_address=wallet.bnb_address,
        ton_address=wallet.ton_address,
        slh_address=wallet.slh_address,
        bnb_balance=float(bnb_balance_dec),
        slh_balance=float(slh_balance_dec),
    )


# --------- ROUTES ---------


@router.post("/set", response_model=schemas.WalletOut)
async def set_wallet(
    payload: schemas.WalletSetIn,
    telegram_id: str = Query(..., description="Telegram user ID"),
    username: Optional[str] = Query(None, description="Telegram username"),
    first_name: Optional[str] = Query(None, description="Telegram first name"),
    db: Session = Depends(get_db),
):
    """
    יצירת/עדכון ארנק עבור משתמש טלגרם.

    query params:
      - telegram_id
      - username (optional)
      - first_name (optional)

    body (JSON):
      - bnb_address (חובה)
      - ton_address (אופציונלי)
    """
    logger.info(
        "Upserting wallet: telegram_id=%s username=%s first_name=%s bnb=%s ton=%s",
        telegram_id,
        username,
        first_name,
        payload.bnb_address,
        payload.ton_address,
    )

    wallet = upsert_wallet(
        db=db,
        telegram_id=telegram_id,
        username=username,
        first_name=first_name,
        bnb_address=payload.bnb_address,
        ton_address=payload.ton_address,
    )
    return wallet


@router.get("/{telegram_id}", response_model=schemas.WalletOut)
async def get_wallet(
    telegram_id: str,
    db: Session = Depends(get_db),
):
    """
    החזרת פרטי ארנק לפי telegram_id.
    """
    wallet = db.get(models.Wallet, telegram_id)
    if not wallet:
        raise HTTPException(status_code=404, detail="Wallet not found")
    return wallet


@router.get("/{telegram_id}/balances", response_model=schemas.BalancesOut)
async def get_balances(
    telegram_id: str,
    db: Session = Depends(get_db),
):
    """
    החזרת יתרות אמיתיות מ-BSC (BNB + SLH) לפי הארנק השמור.
    """
    wallet = db.get(models.Wallet, telegram_id)
    if not wallet:
        raise HTTPException(status_code=404, detail="Wallet not found")

    balances = await get_balances_live(wallet)
    logger.info(
        "Balances for %s – BNB=%s, SLH=%s",
        telegram_id,
        balances.bnb_balance,
        balances.slh_balance,
    )
    return balances
