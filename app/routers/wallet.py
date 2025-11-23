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

# ========= CONFIG =========


def get_config() -> SimpleNamespace:
    """
    קורא משתני סביבה רלוונטיים לרשת BSC ולטוקן SLH.

    נשתמש ישירות ב-RPC של BSC ולא ב-BscScan:
      - BSC_RPC_URL – כתובת RPC (ברירת מחדל: https://bsc-dataseed.binance.org/)
      - SLH_TOKEN_ADDRESS – כתובת חוזה הטוקן SLH
      - SLH_TOKEN_DECIMALS – מספר ספרות אחרי הנקודה (לפי מה שהגדרת, 15)
    """
    return SimpleNamespace(
        BSC_RPC_URL=os.getenv(
            "BSC_RPC_URL", "https://bsc-dataseed.binance.org/"
        ),
        SLH_TOKEN_ADDRESS=os.getenv("SLH_TOKEN_ADDRESS"),
        SLH_TOKEN_DECIMALS=int(os.getenv("SLH_TOKEN_DECIMALS") or "18"),
    )


config = get_config()


# ========= HELPERS: RPC =========


async def _rpc_call(method: str, params: list) -> Optional[str]:
    """
    קריאת JSON-RPC ל-BSC.
    מחזיר את השדה result (hex string) או None במקרה כשל.
    """
    if not config.BSC_RPC_URL:
        logger.error("BSC_RPC_URL is not configured – cannot call RPC")
        return None

    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": method,
        "params": params,
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(config.BSC_RPC_URL, json=payload)
            resp.raise_for_status()
            data = resp.json()
    except Exception as exc:  # noqa: BLE001
        logger.exception("RPC call failed: method=%s error=%s", method, exc)
        return None

    if "error" in data:
        logger.warning("RPC error for %s: %s", method, data["error"])
        return None

    return data.get("result")


async def _fetch_bnb_balance(address: str) -> Decimal:
    """
    מחזיר יתרת BNB אמיתית ב-BNB (לא ב-wei) דרך RPC:
      eth_getBalance(address, 'latest')
    """
    # וידוא כתובת
    if not address or not address.startswith("0x") or len(address) != 42:
        logger.warning("Invalid BNB address: %s", address)
        return Decimal(0)

    result = await _rpc_call("eth_getBalance", [address, "latest"])
    if not result:
        return Decimal(0)

    try:
        # result הוא hex של wei, לדוגמה: "0x1234..."
        wei = int(result, 16)
    except Exception:  # noqa: BLE001
        logger.warning("Invalid hex wei from RPC: %s", result)
        return Decimal(0)

    # 1 BNB = 1e18 wei
    return Decimal(wei) / Decimal("1e18")


def _encode_erc20_balance_of(address: str) -> str:
    """
    בניית data עבור eth_call ל-ERC20 balanceOf(address).

    selector (4 bytes) של balanceOf(address): 0x70a08231
    אחריו 32 bytes של הכתובת (ללא 0x) עם padding מאפסים מימין.
    """
    if not address.startswith("0x"):
        raise ValueError("Address must start with 0x")

    addr_clean = address[2:].lower()
    if len(addr_clean) != 40:
        raise ValueError("Invalid address length for ERC20 balanceOf")

    selector = "70a08231"
    padded_addr = addr_clean.rjust(64, "0")
    return "0x" + selector + padded_addr


async def _fetch_slh_balance(address: str) -> Decimal:
    """
    מחזיר יתרת טוקן SLH אמיתית דרך RPC:
      eth_call ל-contract balanceOf(address)

    משתמש ב:
      SLH_TOKEN_ADDRESS – החוזה
      SLH_TOKEN_DECIMALS – מספר הספרות (למשל 15)
    """
    if not config.SLH_TOKEN_ADDRESS:
        logger.warning("SLH_TOKEN_ADDRESS not configured – returning 0 SLH")
        return Decimal(0)

    if not address or not address.startswith("0x") or len(address) != 42:
        logger.warning("Invalid SLH address (holder): %s", address)
        return Decimal(0)

    try:
        data = _encode_erc20_balance_of(address)
    except ValueError as exc:
        logger.warning("Failed to encode balanceOf data: %s", exc)
        return Decimal(0)

    call_params = [
        {
            "to": config.SLH_TOKEN_ADDRESS,
            "data": data,
        },
        "latest",
    ]

    result = await _rpc_call("eth_call", call_params)
    if not result:
        return Decimal(0)

    try:
        raw = int(result, 16)
    except Exception:  # noqa: BLE001
        logger.warning("Invalid SLH raw balance hex: %s", result)
        return Decimal(0)

    decimals = int(os.getenv("SLH_TOKEN_DECIMALS") or config.SLH_TOKEN_DECIMALS or 18)
    factor = Decimal(10) ** Decimal(decimals)
    if factor == 0:
        return Decimal(0)

    return Decimal(raw) / factor


async def get_balances_live(wallet: models.Wallet) -> schemas.BalancesOut:
    """
    מחזיר BalancesOut עם נתונים חיים מ-BSC:
      - BNB balance (eth_getBalance)
      - SLH balance (eth_call -> balanceOf)

    כרגע TON לא מחושב (נשאיר 0 / כפי שהוא ב-DB).
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

    # BNB + SLH במקביל
    bnb_balance_dec, slh_balance_dec = await asyncio.gather(
        _fetch_bnb_balance(wallet.bnb_address),
        _fetch_slh_balance(wallet.bnb_address),
    )

    logger.info(
        "Live balances for wallet %s -> BNB=%s, SLH=%s",
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


# ========= HELPERS: DB =========


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


# ========= ROUTES =========


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
    משתמש ב-RPC של BSC, לא ב-BscScan.
    """
    wallet = db.get(models.Wallet, telegram_id)
    if not wallet:
        raise HTTPException(status_code=404, detail="Wallet not found")

    balances = await get_balances_live(wallet)
    return balances
