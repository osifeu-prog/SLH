from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class WalletSetIn(BaseModel):
    bnb_address: str = Field(..., description="User BNB address on BSC")
    slh_address: str = Field(..., description="User SLH token address on BSC")


class WalletOut(BaseModel):
    telegram_id: str
    username: Optional[str] = None
    first_name: Optional[str] = None
    bnb_address: Optional[str] = None
    slh_address: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class BalancesOut(BaseModel):
    telegram_id: str
    bnb_address: str | None = None
    slh_address: str | None = None
    bnb_balance: float = 0.0
    slh_balance: float = 0.0