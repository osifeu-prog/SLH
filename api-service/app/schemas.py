from __future__ import annotations

import datetime as dt
from typing import Optional

from pydantic import BaseModel, Field


# ---- Wallet ----

class WalletRegisterIn(BaseModel):
    telegram_id: str
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None

    bnb_address: Optional[str] = None
    slh_address: Optional[str] = None
    slh_ton_address: Optional[str] = None


class WalletOut(BaseModel):
    telegram_id: str
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None

    bnb_address: Optional[str] = None
    slh_address: Optional[str] = None
    slh_ton_address: Optional[str] = None

    created_at: Optional[dt.datetime] = None
    updated_at: Optional[dt.datetime] = None

    class Config:
        orm_mode = True


# ---- Internal Transfers ----

class InternalTransferCreate(BaseModel):
    from_telegram_id: str
    to_telegram_id: str
    amount_slh: float = Field(gt=0)
    memo: Optional[str] = None


class InternalTransferOut(BaseModel):
    id: int
    from_telegram_id: str
    to_telegram_id: str
    amount_slh: float
    memo: Optional[str] = None
    created_at: dt.datetime

    class Config:
        orm_mode = True


# ---- Balances (placeholder; for future integration with BSC / TON) ----

class WalletBalancesOut(BaseModel):
    telegram_id: str
    bnb_address: Optional[str] = None
    slh_address: Optional[str] = None
    slh_ton_address: Optional[str] = None

    bnb_balance: float = 0.0
    slh_balance_chain: float = 0.0
    slh_balance_internal: float = 0.0
