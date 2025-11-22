from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from .. import models, schemas
from ..deps import get_db_session

router = APIRouter(prefix="/api/wallet", tags=["wallet"])


@router.post("/register", response_model=schemas.WalletOut)
def register_wallet(
    payload: schemas.WalletRegisterIn,
    db: Session = Depends(get_db_session),
) -> schemas.WalletOut:
    wallet = db.get(models.Wallet, payload.telegram_id)
    if wallet is None:
        wallet = models.Wallet(
            telegram_id=payload.telegram_id,
            username=payload.username,
            first_name=payload.first_name,
            last_name=payload.last_name,
            bnb_address=payload.bnb_address,
            slh_address=payload.slh_address,
            slh_ton_address=payload.slh_ton_address,
        )
        db.add(wallet)
    else:
        for field in ["username", "first_name", "last_name", "bnb_address", "slh_address", "slh_ton_address"]:
            value = getattr(payload, field)
            if value is not None:
                setattr(wallet, field, value)

    db.commit()
    db.refresh(wallet)
    return wallet


@router.get("/by-telegram/{telegram_id}", response_model=schemas.WalletOut)
def get_wallet_by_telegram(
    telegram_id: str,
    db: Session = Depends(get_db_session),
) -> schemas.WalletOut:
    wallet = db.get(models.Wallet, telegram_id)
    if wallet is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Wallet not found")
    return wallet


@router.get("/{telegram_id}/balances", response_model=schemas.WalletBalancesOut)
def get_balances(
    telegram_id: str,
    db: Session = Depends(get_db_session),
) -> schemas.WalletBalancesOut:
    wallet = db.get(models.Wallet, telegram_id)
    if wallet is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Wallet not found")

    # TODO: integrate with BSC / TON and internal ledger.
    return schemas.WalletBalancesOut(
        telegram_id=wallet.telegram_id,
        bnb_address=wallet.bnb_address,
        slh_address=wallet.slh_address,
        slh_ton_address=wallet.slh_ton_address,
        bnb_balance=0.0,
        slh_balance_chain=0.0,
        slh_balance_internal=0.0,
    )
