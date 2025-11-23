from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from ..db import get_db

router = APIRouter()


@router.post("/register", response_model=schemas.WalletOut)
def register_wallet(payload: schemas.WalletRegisterIn, db: Session = Depends(get_db)):
    """Create or update a wallet for a given Telegram user."""
    wallet = db.get(models.Wallet, payload.telegram_id)
    if wallet is None:
        wallet = models.Wallet(
            telegram_id=payload.telegram_id,
            username=payload.username,
            first_name=payload.first_name,
            last_name=payload.last_name,
            bnb_address=payload.bnb_address,
            slh_address=payload.slh_address,
        )
        db.add(wallet)
    else:
        for field in ["username", "first_name", "last_name", "bnb_address", "slh_address"]:
            value = getattr(payload, field)
            if value is not None:
                setattr(wallet, field, value)

    db.commit()
    db.refresh(wallet)
    return wallet


@router.get("/by-telegram/{telegram_id}", response_model=schemas.WalletOut)
def get_wallet(telegram_id: str, db: Session = Depends(get_db)):
    wallet = db.get(models.Wallet, telegram_id)
    if not wallet:
        raise HTTPException(status_code=404, detail="Wallet not found")
    return wallet


@router.get("/{telegram_id}/balances", response_model=schemas.BalancesOut)
def get_balances(telegram_id: str, db: Session = Depends(get_db)):
    wallet = db.get(models.Wallet, telegram_id)
    if not wallet:
        raise HTTPException(status_code=404, detail="Wallet not found")

    return schemas.BalancesOut(
        telegram_id=telegram_id,
        bnb_address=wallet.bnb_address,
        slh_address=wallet.slh_address,
        slh_internal_balance=0.0,
        slh_bnb_balance=None,
        bnb_balance=None,
    )
