from datetime import datetime

from pydantic import BaseModel


class WalletBase(BaseModel):
    telegram_id: str
    username: str | None = None
    first_name: str | None = None
    bnb_address: str | None = None
    ton_address: str | None = None


class WalletSetIn(BaseModel):
    """Incoming payload for creating/updating a wallet.

    bnb_address – BSC address that will be used for both BNB and SLH.
    ton_address – Optional TON address for identity verification / multi-chain mapping.
    """

    bnb_address: str
    ton_address: str | None = None


class WalletOut(WalletBase):
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True
        from_attributes = True


class BalancesOut(BaseModel):
    telegram_id: str
    bnb_address: str | None = None
    slh_address: str | None = None
    bnb_balance: float = 0.0
    slh_balance: float = 0.0
