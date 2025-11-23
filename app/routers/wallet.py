import asyncio
import logging
import os
from datetime import datetime
from decimal import Decimal
from types import SimpleNamespace
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app import models, schemas
from app.db import get_db

logger = logging.getLogger("slh.wallet")

router = APIRouter(prefix="/api/wallet", tags=["wallet"])

# --------- CONFIG ---------


def get_config() -> SimpleNamespace:
    """
    הגדרות חיבור לרשת BSC ולטוקן SLH מתוך ENV (Railway).
    """
    return SimpleNamespace(
        BSC_RPC_URL=os.getenv("BSC_RPC_URL", "https://bsc-dataseed.binance.org/"),
        SLH_TOKEN_ADDRESS=os.getenv("SLH_TOKEN_ADDRESS"),
        SLH_TOKEN_DECIMALS=int(os.getenv("SLH_TOKEN_DECIMALS") or "18"),
    )


config = get_config()


# --------- HELPERS: RPC ---------


async def _rpc_call(method: str, params: list) -> dict:
    """
    קריאה גנרית ל-RPC של BSC.
    מוסיף לוגים כדי שנוכל לראות מה חוזר בריילווי.
    """
    payload = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}

    rpc_url = config.BSC_RPC_URL
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(rpc_url, json=payload)
        logger.info(
            "RPC call: method=%s status=%s body=%s",
            method,
            resp.status_code,
            resp.text[:500],
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:  # noqa: BLE001
        logger.exception("RPC %s failed to %s: %s", method, rpc_url, exc)
        return {"error": str(exc)}

    if "error" in data:
        logger.warning("RPC %s returned error: %s", method, data["error"])
    return data


def _decode_hex_to_decimal(result: Optional[str]) -> Decimal:
    """
    המרת תוצאה בפורמט hex (0x...) ל-Decimal.
    מחזיר 0 אם משהו לא תקין.
    """
    if not isinstance(result, str) or not result.startswith("0x"):
        logger.warning("Unexpected RPC result (not hex): %r", result)
        return Decimal(0)

    try:
        value_int = int(result, 16)
        return Decimal(value_int)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to parse hex result %r: %s", result, exc)
        return Decimal(0)


def _encode_balance_of_data(address: str) -> str:
    """
    בונה את ה-data ל-balanceOf(address) לפי ABI סטנדרטי:
    keccak256("balanceOf(address)")[:4] = 0x70a08231
    ואז כתובת מפדדת ל-32 bytes.
    """
    addr_clean = address.strip().lower()
    if addr_clean.startswith("0x"):
        addr_clean = addr_clean[2:]

    # לוודא 40 תווים (20 bytes), ואם קצר – padding משמאל
    addr_padded = addr_clean.rjust(64, "0")
    data = "0x70a08231" + addr_padded
    return data


# --------- HELPERS: DB ---------


def upsert_wallet(
    db: Session,
    telegram_id: str,
    username: Optional[str],
    first_name: Optional[str],
    bnb_address: str,
    ton_address: Optional[str] = None,
) -> models.Wallet:
    """
    יוצר או מעדכן רשומת ארנק לפי telegram_id.
    slh_address = bnb_address (אותו ארנק ל-BNB ול-SLH).
    """
    wallet: Optional[models.Wallet] = db.get(models.Wallet, telegram_id)

    if wallet is None:
        wallet = models.Wallet(
            telegram_id=telegram_id,
            username=username,
            first_name=first_name,
            last_name=None,
            bnb_address=bnb_address,
            ton_address=ton_address,
            slh_address=bnb_address,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db.add(wallet)
        logger.info(
            "Created new wallet: telegram_id=%s bnb=%s ton=%s",
            telegram_id,
            bnb_address,
            ton_address,
        )
    else:
        wallet.username = username or wallet.username
        wallet.first_name = first_name or wallet.first_name
        wallet.bnb_address = bnb_address
        wallet.slh_address = bnb_address
        wallet.ton_address = ton_address or wallet.ton_address
        wallet.updated_at = datetime.utcnow()
        logger.info(
            "Updated wallet: telegram_id=%s bnb=%s ton=%s",
            telegram_id,
            bnb_address,
            ton_address,
        )

    db.commit()
    db.refresh(wallet)
    return wallet


# --------- HELPERS: BSC LIVE BALANCES ---------


async def _fetch_bnb_balance(address: str) -> Decimal:
    """
    מחזיר יתרת BNB אמיתית מ-BSC (דרך RPC eth_getBalance).
    """
    if not address:
        return Decimal(0)

    data = await _rpc_call("eth_getBalance", [address, "latest"])
    if "error" in data:
        return Decimal(0)

    raw = _decode_hex_to_decimal(data.get("result"))
    # 1 BNB = 1e18 wei
    return raw / Decimal("1e18")


async def _fetch_slh_balance(address: str) -> Decimal:
    """
    מחזיר יתרת טוקן SLH (BEP-20) לפי החוזה שסיפקת, דרך RPC eth_call.
    """
    if not config.SLH_TOKEN_ADDRESS:
        logger.warning("SLH_TOKEN_ADDRESS not configured – returning 0 SLH")
        return Decimal(0)

    if not address:
        return Decimal(0)

    data_field = _encode_balance_of_data(address)
    call_params = [
        {
            "to": config.SLH_TOKEN_ADDRESS,
            "data": data_field,
        },
        "latest",
    ]

    data = await _rpc_call("eth_call", call_params)
    if "error" in data:
        return Decimal(0)

    raw = _decode_hex_to_decimal(data.get("result"))
    decimals = int(os.getenv("SLH_TOKEN_DECIMALS") or config.SLH_TOKEN_DECIMALS or 18)

    factor = Decimal(10) ** Decimal(decimals)
    if factor == 0:
        return Decimal(0)

    return raw / factor


async def get_balances_live(wallet: models.Wallet) -> schemas.BalancesOut:
    """
    מחזיר BalancesOut עם נתונים חיים מ-BSC דרך RPC.
    כרגע TON לא מחושב (נשאר 0 / כתובת בלבד).
    """
    if not wallet.bnb_address:
        return schemas.BalancesOut(
            telegram_id=wallet.telegram_id,
            bnb_address=None,
            ton_address=wallet.ton_address,
            slh_address=None,
            bnb_balance=0.0,
            slh_balance=0.0,
        )

    bnb_balance_dec, slh_balance_dec = await asyncio.gather(
        _fetch_bnb_balance(wallet.bnb_address),
        _fetch_slh_balance(wallet.bnb_address),
    )

    logger.info(
        "Live balances for %s: BNB=%s, SLH=%s",
        wallet.telegram_id,
        bnb_balance_dec,
        slh_balance_dec,
    )

    return schemas.BalancesOut(
        telegram_id=wallet.telegram_id,
        bnb_address=wallet.bnb_address,
        ton_address=wallet.ton_address,
        slh_address=wallet.slh_address,
        bnb_balance=float(bnb_balance_dec),
        slh_balance=float(slh_balance_dec),
    )


# --------- ROUTES ---------


@router.post("/set", response_model=schemas.WalletOut)
async def set_wallet(
    payload: schemas.WalletSetIn,
    telegram_id: str = Query(..., description="Telegram user ID"),
    username: Optional[str] = Query(None, description="Telegram username"),
    first_name: Optional[str] = Query(None, description="Telegram first name"),
    db: Session = Depends(get_db),
):
    """
    יצירת/עדכון ארנק עבור משתמש טלגרם.

    query params:
      - telegram_id
      - username (optional)
      - first_name (optional)

    body (JSON):
      - bnb_address (חובה)
      - ton_address (אופציונלי)
    """
    logger.info(
        "Upserting wallet: telegram_id=%s username=%s first_name=%s bnb=%s ton=%s",
        telegram_id,
        username,
        first_name,
        payload.bnb_address,
        payload.ton_address,
    )

    wallet = upsert_wallet(
        db=db,
        telegram_id=telegram_id,
        username=username,
        first_name=first_name,
        bnb_address=payload.bnb_address,
        ton_address=payload.ton_address,
    )
    return wallet


@router.get("/{telegram_id}", response_model=schemas.WalletOut)
async def get_wallet(
    telegram_id: str,
    db: Session = Depends(get_db),
):
    """
    החזרת פרטי ארנק לפי telegram_id.
    """
    wallet = db.get(models.Wallet, telegram_id)
    if not wallet:
        raise HTTPException(status_code=404, detail="Wallet not found")
    return wallet


@router.get("/{telegram_id}/balances", response_model=schemas.BalancesOut)
async def get_balances(
    telegram_id: str,
    db: Session = Depends(get_db),
):
    """
    החזרת יתרות אמיתיות מ-BSC (BNB + SLH) לפי הארנק השמור.
    """
    wallet = db.get(models.Wallet, telegram_id)
    if not wallet:
        raise HTTPException(status_code=404, detail="Wallet not found")

    balances = await get_balances_live(wallet)
    return balances
