from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from ..db import get_db

router = APIRouter(prefix="/api/wallet", tags=["wallet"])


@router.post("/set", response_model=schemas.WalletOut)
def set_wallet(
    telegram_id: str,
    username: str | None = None,
    first_name: str | None = None,
    payload: schemas.WalletSetIn | None = None,
    db: Session = Depends(get_db),
) -> schemas.WalletOut:
    """Create or update a wallet row for a Telegram user.

    * telegram_id, username, first_name – מגיעים מה־query string (הבוט / האתר).
    * JSON body כולל:
      - bnb_address: כתובת BSC (משמשת גם ל־BNB וגם ל־SLH).
      - ton_address (אופציונלי): כתובת TON לזיהוי והרשאות.
    """
    if payload is None:
        raise HTTPException(status_code=400, detail="Missing wallet payload")

    if not payload.bnb_address:
        raise HTTPException(status_code=400, detail="bnb_address is required")

    wallet = db.get(models.Wallet, telegram_id)
    if wallet is None:
        wallet = models.Wallet(
            telegram_id=telegram_id,
            username=username,
            first_name=first_name,
        )
        db.add(wallet)

    # עדכון שדות
    if username is not None:
        wallet.username = username
    if first_name is not None:
        wallet.first_name = first_name

    wallet.bnb_address = payload.bnb_address
    # SLH משתמש באותה כתובת BSC – משכפלים
    wallet.slh_address = payload.bnb_address
    wallet.ton_address = payload.ton_address

    db.commit()
    db.refresh(wallet)
    return wallet


@router.get("/{telegram_id}", response_model=schemas.WalletOut)
def get_wallet(telegram_id: str, db: Session = Depends(get_db)) -> schemas.WalletOut:
    """Return wallet row by Telegram ID."""
    wallet = db.get(models.Wallet, telegram_id)
    if wallet is None:
        raise HTTPException(status_code=404, detail="Wallet not found")
    return wallet


@router.get("/{telegram_id}/balances", response_model=schemas.BalancesOut)
def get_balances(telegram_id: str, db: Session = Depends(get_db)) -> schemas.BalancesOut:
    """Placeholder balances endpoint.

    כרגע:
    - מחזיר 0 כיתרות.
    - מחזיר את הכתובות השמורות (BNB / SLH).
    """
    wallet = db.get(models.Wallet, telegram_id)
    if wallet is None:
        raise HTTPException(status_code=404, detail="Wallet not found")

    return schemas.BalancesOut(
        telegram_id=wallet.telegram_id,
        bnb_address=wallet.bnb_address,
        slh_address=wallet.slh_address or wallet.bnb_address,
        bnb_balance=0.0,
        slh_balance=0.0,
    )
