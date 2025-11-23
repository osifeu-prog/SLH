from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class WalletRegisterIn(BaseModel):
    telegram_id: str
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    bnb_address: Optional[str] = None
    slh_address: Optional[str] = None


class WalletOut(BaseModel):
    telegram_id: str
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    bnb_address: Optional[str] = None
    slh_address: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class BalancesOut(BaseModel):
    telegram_id: str
    bnb_address: Optional[str]
    slh_address: Optional[str]
    slh_internal_balance: float = 0.0
    slh_bnb_balance: Optional[float] = None
    bnb_balance: Optional[float] = None
