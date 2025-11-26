
from typing import Optional

from pydantic import BaseModel


class WalletSetIn(BaseModel):
    bnb_address: str
    ton_address: Optional[str] = None
    slh_address: Optional[str] = None
    username: Optional[str] = None
    first_name: Optional[str] = None


class WalletOut(BaseModel):
    telegram_id: str
    bnb_address: Optional[str]
    ton_address: Optional[str]
    slh_address: Optional[str]
    username: Optional[str]
    first_name: Optional[str]

    class Config:
        orm_mode = True


class BalancesOut(BaseModel):
    telegram_id: str
    bnb_address: Optional[str]
    ton_address: Optional[str]
    slh_address: Optional[str]
    bnb_balance: float = 0.0
    slh_balance: float = 0.0            # total (on-chain + internal)
    slh_balance_onchain: float = 0.0
    slh_balance_internal: float = 0.0
