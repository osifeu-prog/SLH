import os
import logging
import asyncio
from decimal import Decimal
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Wallet
from app.schemas import WalletSetIn, WalletOut, BalancesOut

logger = logging.getLogger("slh.wallet")

router = APIRouter(
    prefix="/api/wallet",
    tags=["wallet"],
)

# === BSC / SLH config from environment ===
BSC_API_BASE = "https://api.bscscan.com/api"
BSCSCAN_API_KEY = os.getenv("BSCSCAN_API_KEY", "").strip()
SLH_TOKEN_ADDRESS = os.getenv("SLH_TOKEN_ADDRESS", "").strip()  # 0xACb0...
BNB_DECIMALS = 18
SLH_DECIMALS = int(os.getenv("SLH_TOKEN_DECIMALS", "18"))  # אם תרצה לשנות בעתיד


# ---------- Helpers for on-chain balances (BscScan) ----------


async def _fetch_bnb_balance(address: str, client: httpx.AsyncClient) -> Decimal:
    """
    Return BNB balance (in whole units) for a given address on BSC mainnet.
    Uses BscScan account balance endpoint.
    """
    if not address:
        return Decimal("0")

    if not BSCSCAN_API_KEY:
        logger.warning("BSCSCAN_API_KEY not configured – returning 0 BNB balance")
        return Decimal("0")

    params = {
        "module": "account",
        "action": "balance",
        "address": address,
        "tag": "latest",
        "apikey": BSCSCAN_API_KEY,
    }

    try:
        resp = await client.get(BSC_API_BASE, params=params)
        resp.raise_for_status()
        data = resp.json()
        if data.get("status") != "1":
            logger.warning("BscScan BNB error for %s: %s", address, data)
            return Decimal("0")

        raw = data.get("result", "0") or "0"
        # BNB has 18 decimals
        return (Decimal(raw) / (Decimal(10) ** BNB_DECIMALS)).quantize(Decimal("0.00000001"))
    except Exception as e:
        logger.exception("Failed to fetch BNB balance for %s: %s", address, e)
        return Decimal("0")


async def _fetch_slh_balance(address: str, client: httpx.AsyncClient) -> Decimal:
    """
    Return SLH token balance (in whole units) for a given address on BSC mainnet.
    Uses BscScan tokenbalance endpoint with the SLH contract.
    """
    if not address:
        return Decimal("0")

    if not (BSCSCAN_API_KEY and SLH_TOKEN_ADDRESS):
        logger.warning(
            "BSCSCAN_API_KEY or SLH_TOKEN_ADDRESS not configured – returning 0 SLH balance"
        )
        return Decimal("0")

    params = {
        "module": "account",
        "action": "tokenbalance",
        "contractaddress": SLH_TOKEN_ADDRESS,
        "address": address,
        "tag": "latest",
        "apikey": BSCSCAN_API_KEY,
    }

    try:
        resp = await client.get(BSC_API_BASE, params=params)
        resp.raise_for_status()
        data = resp.json()
        if data.get("status") != "1":
            logger.warning("BscScan SLH error for %s: %s", address, data)
            return Decimal("0")

        raw = data.get("result", "0") or "0"
        # SLH – נניח 18 ספרות אחרי הנקודה (כמו רוב ERC20/BEP20)
        return (Decimal(raw) / (Decimal(10) ** SLH_DECIMALS)).quantize(Decimal("0.00000001"))
    except Exception as e:
        logger.exception("Failed to fetch SLH balance for %s: %s", address, e)
        return Decimal("0")


async def get_onchain_balances(address: Optional[str]) -> tuple[Decimal, Decimal]:
    """
    Fetch both BNB and SLH balances for the given address, using BscScan.
    Returns (bnb_balance, slh_balance) in whole units.
    """
    if not address:
        return Decimal("0"), Decimal("0")

    if not BSCSCAN_API_KEY:
        logger.warning("BSCSCAN_API_KEY missing – returning 0 balances")
        return Decimal("0"), Decimal("0")

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            bnb_task = _fetch_bnb_balance(address, client)
            slh_task = _fetch_slh_balance(address, client)
            bnb_balance, slh_balance = await asyncio.gather(bnb_task, slh_task)
            return bnb_balance, slh_balance
    except Exception as e:
        logger.exception("Failed to fetch on-chain balances for %s: %s", address, e)
        return Decimal("0"), Decimal("0")


# ---------- API endpoints ----------


@router.post("/set", response_model=WalletOut)
def set_wallet(
    wallet_in: WalletSetIn,
    telegram_id: str,
    username: Optional[str] = None,
    first_name: Optional[str] = None,
    db: Session = Depends(get_db),
) -> WalletOut:
    """
    Create or update a wallet row for a Telegram user.

    - telegram_id, username, first_name מגיעים מה־query string (מהבוט או מהאתר)
    - גוף הבקשה (JSON) כולל:
        bnb_address – הכתובת ב-BSC (משמשת גם ל-BNB וגם ל-SLH)
        ton_address – אופציונלי, כתובת TON לאימות זהות
    """
    logger.info(
        "Upserting wallet: telegram_id=%s username=%s first_name=%s bnb=%s ton=%s",
        telegram_id,
        username,
        first_name,
        wallet_in.bnb_address,
        wallet_in.ton_address,
    )

    wallet = db.get(Wallet, telegram_id)
    if wallet is None:
        wallet = Wallet(telegram_id=str(telegram_id))
        db.add(wallet)

    wallet.username = username or wallet.username
    wallet.first_name = first_name or wallet.first_name
    wallet.bnb_address = wallet_in.bnb_address
    wallet.ton_address = wallet_in.ton_address
    # כרגע SLH באותה כתובת כמו BNB – אפשר לשנות בעתיד אם תרצה
    wallet.slh_address = wallet_in.bnb_address

    db.commit()
    db.refresh(wallet)
    return WalletOut.from_orm(wallet)


@router.get("/{telegram_id}", response_model=WalletOut)
def get_wallet(telegram_id: str, db: Session = Depends(get_db)) -> WalletOut:
    """
    Get stored wallet info for a Telegram user.
    """
    wallet = db.get(Wallet, telegram_id)
    if wallet is None:
        raise HTTPException(status_code=404, detail="Wallet not found")

    return WalletOut.from_orm(wallet)


@router.get("/{telegram_id}/balances", response_model=BalancesOut)
async def get_balances(telegram_id: str, db: Session = Depends(get_db)) -> BalancesOut:
    """
    Get on-chain balances (BNB + SLH) for the stored BNB/SLH address.
    - קורא ל-BscScan כדי להביא יתרות אמיתיות.
    """
    wallet = db.get(Wallet, telegram_id)
    if wallet is None:
        raise HTTPException(status_code=404, detail="Wallet not found")

    if not wallet.bnb_address:
        raise HTTPException(status_code=400, detail="Wallet has no BNB/SLH address")

    bnb_balance, slh_balance = await get_onchain_balances(wallet.bnb_address)

    return BalancesOut(
        telegram_id=wallet.telegram_id,
        bnb_address=wallet.bnb_address,
        slh_address=wallet.slh_address or wallet.bnb_address,
        bnb_balance=float(bnb_balance),
        slh_balance=float(slh_balance),
    )
