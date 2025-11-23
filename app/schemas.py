
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field

class WalletSetIn(BaseModel):
    bnb_address: str = Field(..., description="BSC address (used for both BNB and SLH)")
    ton_address: Optional[str] = Field(
        None,
        description="Optional TON address for identity verification",
    )

class WalletOut(BaseModel):
    telegram_id: str
    username: Optional[str] = None
    first_name: Optional[str] = None
    bnb_address: str
    ton_address: Optional[str] = None
    slh_address: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class BalancesOut(BaseModel):
    telegram_id: str
    bnb_address: str
    slh_address: str
    ton_address: Optional[str] = None
    bnb_balance: float = 0.0
    slh_balance: float = 0.0
