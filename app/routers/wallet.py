import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..db import get_db
from .. import models, schemas

logger = logging.getLogger("slh.wallet")

router = APIRouter(
    prefix="/api/wallet",
    tags=["wallet"],
)


@router.post("/set", response_model=schemas.WalletOut)
def set_wallet(
    telegram_id: str,
    username: str | None = None,
    first_name: str | None = None,
    payload: schemas.WalletSetIn | None = None,
    db: Session = Depends(get_db),
):
    """Create or update a wallet row for a Telegram user.

    Called both by the bot and by HTTP clients.
    """
    if payload is None:
        raise HTTPException(status_code=400, detail="Missing wallet payload")

    wallet = db.get(models.Wallet, telegram_id)
    if not wallet:
        wallet = models.Wallet(
            telegram_id=telegram_id,
            username=username,
            first_name=first_name,
            bnb_address=payload.bnb_address,
            slh_address=payload.slh_address,
        )
        db.add(wallet)
    else:
        wallet.username = username or wallet.username
        wallet.first_name = first_name or wallet.first_name
        wallet.bnb_address = payload.bnb_address
        wallet.slh_address = payload.slh_address

    db.commit()
    db.refresh(wallet)
    return wallet


@router.get("/{telegram_id}", response_model=schemas.WalletOut)
def get_wallet(
    telegram_id: str,
    db: Session = Depends(get_db),
):
    wallet = db.get(models.Wallet, telegram_id)
    if not wallet:
        raise HTTPException(status_code=404, detail="Wallet not found")
    return wallet


@router.get("/{telegram_id}/balances", response_model=schemas.BalancesOut)
def get_balances(
    telegram_id: str,
    db: Session = Depends(get_db),
):
    """Placeholder balance endpoint.

    Right now returns 0 for on-chain balances and just echoes addresses.
    Later you can plug BscScan / TON APIs here.
    """
    wallet = db.get(models.Wallet, telegram_id)
    if not wallet:
        raise HTTPException(status_code=404, detail="Wallet not found")

    return schemas.BalancesOut(
        telegram_id=wallet.telegram_id,
        bnb_address=wallet.bnb_address,
        slh_address=wallet.slh_address,
        bnb_balance=0.0,
        slh_balance=0.0,
    )