
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from ..db import get_db
from .. import models, schemas

router = APIRouter(prefix="/api/wallet", tags=["wallet"])

@router.post("/set", response_model=schemas.WalletOut)
def set_wallet(
    wallet_in: schemas.WalletSetIn,
    telegram_id: str = Query(..., description="Telegram user ID"),
    username: str | None = Query(None, description="Telegram username"),
    first_name: str | None = Query(None, description="Telegram first name"),
    db: Session = Depends(get_db),
):
    wallet = db.get(models.Wallet, telegram_id)

    if wallet is None:
        wallet = models.Wallet(
            telegram_id=str(telegram_id),
            username=username,
            first_name=first_name,
            bnb_address=wallet_in.bnb_address,
            ton_address=wallet_in.ton_address,
            slh_address=wallet_in.bnb_address,
        )
        db.add(wallet)
    else:
        wallet.username = username or wallet.username
        wallet.first_name = first_name or wallet.first_name
        wallet.bnb_address = wallet_in.bnb_address
        wallet.ton_address = wallet_in.ton_address
        wallet.slh_address = wallet_in.bnb_address

    db.commit()
    db.refresh(wallet)
    return wallet

@router.get("/{telegram_id}", response_model=schemas.WalletOut)
def get_wallet(
    telegram_id: str,
    db: Session = Depends(get_db),
):
    wallet = db.get(models.Wallet, telegram_id)
    if wallet is None:
        raise HTTPException(status_code=404, detail="Wallet not found")
    return wallet

@router.get("/{telegram_id}/balances", response_model=schemas.BalancesOut)
def get_balances(
    telegram_id: str,
    db: Session = Depends(get_db),
):
    wallet = db.get(models.Wallet, telegram_id)
    if wallet is None:
        raise HTTPException(status_code=404, detail="Wallet not found")

    # Placeholder – later you will plug BscScan / TON / SLH indexer here.
    return schemas.BalancesOut(
        telegram_id=wallet.telegram_id,
        bnb_address=wallet.bnb_address,
        slh_address=wallet.slh_address or wallet.bnb_address,
        ton_address=wallet.ton_address,
        bnb_balance=0.0,
        slh_balance=0.0,
    )
