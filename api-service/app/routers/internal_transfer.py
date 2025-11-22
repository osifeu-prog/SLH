from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from .. import models, schemas
from ..deps import get_db_session

router = APIRouter(prefix="/api/internal", tags=["internal-transfer"])


@router.post("/transfer", response_model=schemas.InternalTransferOut)
def internal_transfer(
    payload: schemas.InternalTransferCreate,
    db: Session = Depends(get_db_session),
) -> schemas.InternalTransferOut:
    if payload.from_telegram_id == payload.to_telegram_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot transfer to self")

    from_wallet = db.get(models.Wallet, payload.from_telegram_id)
    to_wallet = db.get(models.Wallet, payload.to_telegram_id)
    if not from_wallet or not to_wallet:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Wallet not found")

    transfer = models.InternalTransfer(
        from_telegram_id=payload.from_telegram_id,
        to_telegram_id=payload.to_telegram_id,
        amount_slh=payload.amount_slh,
        memo=payload.memo,
    )
    db.add(transfer)
    db.commit()
    db.refresh(transfer)
    return transfer
