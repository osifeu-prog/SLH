from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Wallet
from .. import schemas

logger = logging.getLogger("slh.wallet")

router = APIRouter(
    prefix="/api/wallet",
    tags=["wallet"],
)


def _normalize_address(addr: Optional[str]) -> Optional[str]:
    """
    ניקוי כתובת – מסיר רווחים, משאיר None אם ריק.
    """
    if addr is None:
        return None
    addr = addr.strip()
    return addr or None


@router.post(
    "/set",
    response_model=schemas.WalletOut,
    summary="Set Wallet",
    description=(
        "Create or update a wallet row for a Telegram user.\n\n"
        "- telegram_id, username, first_name מגיעים מה־query string (מהבוט או מהאתר)\n"
        "- גוף הבקשה (JSON) כולל:\n"
        "  * bnb_address – הכתובת ב-BSC (משמשת גם ל-BNB וגם ל-SLH)\n"
        "  * ton_address – אופציונלי, כתובת TON לאימות זהות\n"
    ),
)
async def set_wallet(
    telegram_id: str,
    username: Optional[str] = None,
    first_name: Optional[str] = None,
    payload: schemas.WalletSetIn = ...,
    db: Session = Depends(get_db),
) -> schemas.WalletOut:
    """
    יצירה / עדכון של ארנק למשתמש לפי telegram_id.

    אם הרשומה קיימת – מעדכנים כתובות ושדות פרופיל.
    אם לא קיימת – יוצרים חדשה.
    """
    telegram_id = str(telegram_id).strip()
    if not telegram_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="telegram_id is required",
        )

    bnb_address = _normalize_address(payload.bnb_address)
    ton_address = _normalize_address(payload.ton_address)

    if not bnb_address:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="bnb_address is required",
        )

    username = username.strip() if username else None
    first_name = first_name.strip() if first_name else None

    logger.info(
        "Upserting wallet: telegram_id=%s username=%s first_name=%s bnb=%s ton=%s",
        telegram_id,
        username,
        first_name,
        bnb_address,
        ton_address,
    )

    wallet = db.get(Wallet, telegram_id)
    if wallet is None:
        # יצירה
        wallet = Wallet(
            telegram_id=telegram_id,
            username=username,
            first_name=first_name,
            bnb_address=bnb_address,
            ton_address=ton_address,
        )
        db.add(wallet)
    else:
        # עדכון
        wallet.username = username or wallet.username
        wallet.first_name = first_name or wallet.first_name
        wallet.bnb_address = bnb_address
        wallet.ton_address = ton_address

    db.commit()
    db.refresh(wallet)

    return schemas.WalletOut.model_validate(wallet)


@router.get(
    "/{telegram_id}",
    response_model=schemas.WalletOut,
    summary="Get Wallet",
)
async def get_wallet(
    telegram_id: str,
    db: Session = Depends(get_db),
) -> schemas.WalletOut:
    """
    החזרת ארנק לפי telegram_id.
    """
    telegram_id = str(telegram_id).strip()
    wallet = db.get(Wallet, telegram_id)
    if wallet is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Wallet not found",
        )
    return schemas.WalletOut.model_validate(wallet)


@router.get(
    "/{telegram_id}/balances",
    response_model=schemas.BalancesOut,
    summary="Get Balances",
    description=(
        "Placeholder balance endpoint.\n\n"
        "כרגע מחזיר 0 ל-BNB ול-SLH, ומחזיר את הכתובות כמו שהן.\n"
        "בהמשך נוסיף BscScan / RPC + TON לקריאת יתרות אמת."
    ),
)
async def get_balances(
    telegram_id: str,
    db: Session = Depends(get_db),
) -> schemas.BalancesOut:
    telegram_id = str(telegram_id).strip()
    wallet = db.get(Wallet, telegram_id)
    if wallet is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Wallet not found",
        )

    return schemas.BalancesOut(
        telegram_id=wallet.telegram_id,
        bnb_address=wallet.bnb_address or "",
        ton_address=wallet.ton_address,
        bnb_balance=0.0,
        slh_balance=0.0,
    )
