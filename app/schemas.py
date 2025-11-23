from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, ConfigDict


class WalletBase(BaseModel):
    """
    Base schema for a user's wallet.

    bnb_address  – BSC address (משמש גם ל-BNB וגם ל-SLH באותה כתובת).
    ton_address  – כתובת TON לאימות זהות / שימושים עתידיים.
    """

    bnb_address: str = Field(
        ...,
        description="BSC wallet address that holds BNB and SLH on BSC.",
        examples=["0xd0617b54fb4b6b66307846f217b4d685800e3da4"],
    )
    ton_address: Optional[str] = Field(
        None,
        description="TON wallet address for identity verification.",
        examples=["UQCXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX"],
    )


class WalletSetIn(WalletBase):
    """
    Input schema for creating/updating a wallet.

    כרגע ה־API והשירותי טלגרם משתמשים באותה סכימה:
    - תמיד חובה bnb_address.
    - ton_address אופציונלי.
    """
    pass


class WalletOut(WalletBase):
    """
    Full wallet row as returned from the API.
    """

    model_config = ConfigDict(from_attributes=True)

    telegram_id: str = Field(..., description="Telegram user ID as string.")
    username: Optional[str] = Field(
        None,
        description="Telegram @username if available.",
    )
    first_name: Optional[str] = Field(
        None,
        description="Telegram first name.",
    )
    created_at: datetime = Field(..., description="Row creation time (UTC).")
    updated_at: datetime = Field(..., description="Last update time (UTC).")


class BalancesOut(BaseModel):
    """
    Placeholder balances response.

    בשלב הבא נתחבר ל-BscScan / RPC ול-TON כדי להחזיר יתרות אמת.
    כרגע מחזירים 0 ונותנים תשתית.
    """

    model_config = ConfigDict(from_attributes=True)

    telegram_id: str
    bnb_address: str
    ton_address: Optional[str] = None

    bnb_balance: float = Field(
        0.0,
        description="BNB balance on-chain (placeholder for now).",
    )
    slh_balance: float = Field(
        0.0,
        description="SLH token balance on-chain (placeholder for now).",
    )
