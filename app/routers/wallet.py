import logging
import os
from typing import Optional, Tuple

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app import models, schemas  # שים לב: לא from . import ...

from app.db import get_db

logger = logging.getLogger("slh.wallet")

router = APIRouter(prefix="/api/wallet", tags=["wallet"])


# ===== Helpers for BscScan =====

BSCSCAN_API_URL = "https://api.bscscan.com/api"
BSCSCAN_API_KEY = os.getenv("BSCSCAN_API_KEY") or ""
SLH_TOKEN_ADDRESS = os.getenv("SLH_TOKEN_ADDRESS") or ""
# דיפולט 18 אם לא הוגדר, אצלך הגדרת 15
try:
    SLH_TOKEN_DECIMALS = int(os.getenv("SLH_TOKEN_DECIMALS", "18"))
except ValueError:
    SLH_TOKEN_DECIMALS = 18


def _normalize_decimal(value_str: str, decimals: int) -> float:
    try:
        raw = int(value_str)
        return raw / (10 ** decimals)
    except Exception:
        return 0.0


def _fetch_bnb_and_slh_balances(address: str) -> Tuple[float, float]:
    """
    מושך יתרות מ-BscScan:
    - BNB native (18 decimals)
    - SLH token לפי החוזה שהוגדר ב-SLH_TOKEN_ADDRESS
    """
    if not BSCSCAN_API_KEY or not SLH_TOKEN_ADDRESS:
        logger.warning(
            "BscScan disabled: BSCSCAN_API_KEY or SLH_TOKEN_ADDRESS not configured."
        )
        return 0.0, 0.0

    bnb_balance = 0.0
    slh_balance = 0.0

    try:
        # --- BNB balance ---
        params_bnb = {
            "module": "account",
            "action": "balance",
            "address": address,
            "apikey": BSCSCAN_API_KEY,
        }
        with httpx.Client(timeout=10) as client:
            resp_bnb = client.get(BSCSCAN_API_URL, params=params_bnb)
        resp_bnb.raise_for_status()
        data_bnb = resp_bnb.json()
        if data_bnb.get("status") == "1":
            bnb_balance = _normalize_decimal(data_bnb.get("result", "0"), 18)
        else:
            logger.warning("BscScan BNB response NOTOK: %s", data_bnb)

        # --- SLH token balance ---
        params_slh = {
            "module": "account",
            "action": "tokenbalance",
            "contractaddress": SLH_TOKEN_ADDRESS,
            "address": address,
            "tag": "latest",
            "apikey": BSCSCAN_API_KEY,
        }
        with httpx.Client(timeout=10) as client:
            resp_slh = client.get(BSCSCAN_API_URL, params=params_slh)
        resp_slh.raise_for_status()
        data_slh = resp_slh.json()
        if data_slh.get("status") == "1":
            slh_balance = _normalize_decimal(
                data_slh.get("result", "0"), SLH_TOKEN_DECIMALS
            )
        else:
            logger.warning("BscScan SLH response NOTOK: %s", data_slh)

    except Exception as e:  # noqa: BLE001
        logger.exception("Error fetching balances from BscScan: %s", e)

    return bnb_balance, slh_balance


# ===== Routes =====


@router.post("/set", response_model=schemas.WalletOut)
def set_wallet(
    wallet_in: schemas.WalletSetIn,
    telegram_id: str = Query(..., description="Telegram user ID"),
    username: Optional[str] = Query(None, description="Telegram username"),
    first_name: Optional[str] = Query(None, description="Telegram first name"),
    db: Session = Depends(get_db),
) -> schemas.WalletOut:
    """
    יצירה / עדכון ארנק למשתמש טלגרם.
    - מקבל query params: telegram_id, username, first_name
    - גוף JSON: bnb_address, ton_address (אופציונלי)
    """
    logger.info(
        "Upserting wallet: telegram_id=%s username=%s first_name=%s bnb=%s ton=%s",
        telegram_id,
        username,
        first_name,
        wallet_in.bnb_address,
        wallet_in.ton_address,
    )

    wallet = db.get(models.Wallet, telegram_id)

    if wallet is None:
        wallet = models.Wallet(
            telegram_id=telegram_id,
            username=username or "",
            first_name=first_name or "",
            bnb_address=wallet_in.bnb_address,
            ton_address=wallet_in.ton_address,
        )
        db.add(wallet)
    else:
        wallet.username = username or wallet.username
        wallet.first_name = first_name or wallet.first_name
        wallet.bnb_address = wallet_in.bnb_address
        wallet.ton_address = wallet_in.ton_address

    db.commit()
    db.refresh(wallet)

    return schemas.WalletOut.from_orm(wallet)


@router.get("/{telegram_id}", response_model=schemas.WalletOut)
def get_wallet(
    telegram_id: str, db: Session = Depends(get_db)
) -> schemas.WalletOut:
    """
    החזרת נתוני הארנק השמורים למשתמש (ללא שאלית רשת).
    """
    wallet = db.get(models.Wallet, telegram_id)
    if wallet is None:
        raise HTTPException(status_code=404, detail="Wallet not found")

    return schemas.WalletOut.from_orm(wallet)


@router.get("/{telegram_id}/balances", response_model=schemas.BalancesOut)
def get_balances(
    telegram_id: str, db: Session = Depends(get_db)
) -> schemas.BalancesOut:
    """
    החזרת יתרות אמיתיות (BNB + SLH) מהבלוקצ'יין + הכתובות השמורות.

    - מושך את הארנק מה-DB לפי telegram_id.
    - אם אין כתובת BNB – מחזיר 0.
    - אם יש BNB address ויש הגדרות BscScan – מושך יתרות אמיתיות.
    """
    wallet = db.get(models.Wallet, telegram_id)
    if wallet is None:
        raise HTTPException(status_code=404, detail="Wallet not found")

    bnb_balance = 0.0
    slh_balance = 0.0

    if wallet.bnb_address:
        bnb_balance, slh_balance = _fetch_bnb_and_slh_balances(wallet.bnb_address)

    return schemas.BalancesOut(
        telegram_id=wallet.telegram_id,
        bnb_address=wallet.bnb_address,
        ton_address=wallet.ton_address,
        slh_address=wallet.slh_address,
        bnb_balance=bnb_balance,
        slh_balance=slh_balance,
    )
