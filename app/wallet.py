from decimal import Decimal
from typing import Optional

import asyncio
import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app import models, schemas
from app.config import settings
from app.db import get_db

router = APIRouter(prefix="/api/wallet", tags=["wallet"])


async def _rpc_call(method: str, params: list) -> Optional[str]:
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": method,
        "params": params,
    }

    rpc_url = settings.BSC_RPC_URL
    timeout = httpx.Timeout(10.0, connect=5.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        try:
            resp = await client.post(rpc_url, json=payload)
            resp.raise_for_status()
            data = resp.json()
            return data.get("result")
        except Exception:
            return None


def _decode_hex_to_decimal(value_hex: Optional[str], decimals: int) -> Decimal:
    if not value_hex:
        return Decimal("0")
    if value_hex.startswith("0x"):
        value_hex = value_hex[2:]
    try:
        wei_int = int(value_hex or "0", 16)
    except ValueError:
        return Decimal("0")
    factor = Decimal(10) ** decimals
    return (Decimal(wei_int) / factor).quantize(Decimal("0.000000000000000001"))


async def _fetch_bnb_balance(address: str) -> Decimal:
    result = await _rpc_call("eth_getBalance", [address, "latest"])
    return _decode_hex_to_decimal(result, 18)


async def _fetch_slh_balance(address: str) -> Decimal:
    token = settings.SLH_TOKEN_ADDRESS
    if not token:
        return Decimal("0")

    data = (
        "0x70a08231"
        + "0" * 24
        + address.lower().replace("0x", "")
    )

    result = await _rpc_call(
        "eth_call",
        [
            {
                "to": token,
                "data": data,
            },
            "latest",
        ],
    )
    return _decode_hex_to_decimal(result, settings.SLH_TOKEN_DECIMALS)


async def _get_internal_slh_balance(db: Session, telegram_id: str) -> Decimal:
    incoming = (
        db.query(func.coalesce(func.sum(models.Transaction.amount), 0))
        .filter(
            models.Transaction.to_telegram_id == telegram_id,
            models.Transaction.currency == "SLH",
            models.Transaction.chain == "INTERNAL",
        )
        .scalar()
    )
    outgoing = (
        db.query(func.coalesce(func.sum(models.Transaction.amount), 0))
        .filter(
            models.Transaction.from_telegram_id == telegram_id,
            models.Transaction.currency == "SLH",
            models.Transaction.chain == "INTERNAL",
        )
        .scalar()
    )

    inc = Decimal(incoming or 0)
    out = Decimal(outgoing or 0)
    return (inc - out).quantize(Decimal("0.000000000000000001"))


async def get_balances_live(wallet: models.Wallet, db: Session) -> schemas.BalancesOut:
    internal_slh = await _get_internal_slh_balance(db, wallet.telegram_id)

    if not wallet.bnb_address:
        total_slh = internal_slh
        return schemas.BalancesOut(
            telegram_id=wallet.telegram_id,
            bnb_address=None,
            ton_address=wallet.ton_address,
            slh_address=wallet.slh_address,
            bnb_balance=0.0,
            slh_balance=float(total_slh),
            slh_balance_onchain=0.0,
            slh_balance_internal=float(internal_slh),
        )

    bnb_balance_dec, slh_balance_dec = await asyncio.gather(
        _fetch_bnb_balance(wallet.bnb_address),
        _fetch_slh_balance(wallet.slh_address or wallet.bnb_address),
    )

    total_slh = slh_balance_dec + internal_slh

    return schemas.BalancesOut(
        telegram_id=wallet.telegram_id,
        bnb_address=wallet.bnb_address,
        ton_address=wallet.ton_address,
        slh_address=wallet.slh_address or wallet.bnb_address,
        bnb_balance=float(bnb_balance_dec),
        slh_balance=float(total_slh),
        slh_balance_onchain=float(slh_balance_dec),
        slh_balance_internal=float(internal_slh),
    )


@router.post("/set", response_model=schemas.WalletOut)
async def set_wallet(
    payload: schemas.WalletSetIn,
    telegram_id: str = Query(..., description="Telegram user id"),
    username: Optional[str] = Query(None),
    first_name: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    wallet = (
        db.query(models.Wallet)
        .filter(models.Wallet.telegram_id == telegram_id)
        .first()
    )

    if wallet is None:
        wallet = models.Wallet(
            telegram_id=str(telegram_id),
            bnb_address=payload.bnb_address,
            slh_address=payload.slh_address or payload.bnb_address,
            ton_address=payload.ton_address,
            username=username or payload.username,
            first_name=first_name or payload.first_name,
            is_active=True,
        )
        db.add(wallet)
    else:
        wallet.bnb_address = payload.bnb_address or wallet.bnb_address
        wallet.slh_address = (
            payload.slh_address or wallet.slh_address or wallet.bnb_address
        )
        wallet.ton_address = payload.ton_address or wallet.ton_address
        wallet.username = username or payload.username or wallet.username
        wallet.first_name = first_name or payload.first_name or wallet.first_name

    db.commit()
    db.refresh(wallet)
    return wallet


@router.get("/{telegram_id}", response_model=schemas.WalletOut)
async def get_wallet(telegram_id: str, db: Session = Depends(get_db)):
    wallet = (
        db.query(models.Wallet)
        .filter(models.Wallet.telegram_id == telegram_id)
        .first()
    )
    if wallet is None:
        raise HTTPException(status_code=404, detail="Wallet not found")
    return wallet


@router.get("/{telegram_id}/balances", response_model=schemas.BalancesOut)
async def get_balances(telegram_id: str, db: Session = Depends(get_db)):
    wallet = (
        db.query(models.Wallet)
        .filter(models.Wallet.telegram_id == telegram_id)
        .first()
    )
    if wallet is None:
        raise HTTPException(status_code=404, detail="Wallet not found")

    return await get_balances_live(wallet, db)
