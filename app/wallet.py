from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from .db import get_db
from .models import Wallet
from .schemas import WalletSetIn, WalletOut, BalancesOut

router = APIRouter(prefix="/api/wallet", tags=["wallet"])


def upsert_wallet(
    db: Session,
    telegram_id: str,
    username: Optional[str],
    first_name: Optional[str],
    bnb_address: str,
    ton_address: Optional[str] = None,
) -> Wallet:
    wallet = db.get(Wallet, telegram_id)
    if wallet is None:
        wallet = Wallet(telegram_id=telegram_id)

    # עדכון נתונים
    if username:
        wallet.username = username
    if first_name:
        wallet.first_name = first_name

    wallet.bnb_address = bnb_address
    # SLH כרגע זהה ל-BNB
    wallet.slh_address = bnb_address
    if ton_address:
        wallet.ton_address = ton_address

    db.add(wallet)
    db.commit()
    db.refresh(wallet)
    return wallet


@router.post("/set", response_model=WalletOut)
def set_wallet(
    payload: WalletSetIn,
    telegram_id: str = Query(..., description="Telegram user id as string"),
    username: Optional[str] = Query(None),
    first_name: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    try:
        wallet = upsert_wallet(
            db=db,
            telegram_id=telegram_id,
            username=username,
            first_name=first_name,
            bnb_address=payload.bnb_address,
            ton_address=payload.ton_address,
        )
    except Exception as e:
        # לוג לשרת, אבל החוצה מחזירים 500 סטנדרטי
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal wallet error",
        ) from e
    return wallet


@router.get("/{telegram_id}", response_model=WalletOut)
def get_wallet(
    telegram_id: str,
    db: Session = Depends(get_db),
):
    wallet = db.get(Wallet, telegram_id)
    if wallet is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Wallet not found")
    return wallet


@router.get("/{telegram_id}/balances", response_model=BalancesOut)
def get_balances(
    telegram_id: str,
    db: Session = Depends(get_db),
):
    wallet = db.get(Wallet, telegram_id)
    if wallet is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Wallet not found")

    # כרגע מחזירים 0 כ-placeholder, אפשר לחבר ל-BscScan / TON APIs
    return BalancesOut(
        telegram_id=wallet.telegram_id,
        bnb_address=wallet.bnb_address,
        ton_address=wallet.ton_address,
        slh_address=wallet.slh_address,
        bnb_balance=0.0,
        slh_balance=0.0,
    )
