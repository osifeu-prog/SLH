
from datetime import datetime
from sqlalchemy import Column, DateTime, String, Integer, Boolean, Numeric, ForeignKey
from .db import Base

class Wallet(Base):
    __tablename__ = "wallets"

    telegram_id = Column(String, primary_key=True, index=True)
    username = Column(String, nullable=True)
    first_name = Column(String, nullable=True)
    last_name = Column(String, nullable=True)

    # One BSC address used for both BNB and SLH
    bnb_address = Column(String, nullable=False)

    # Optional TON address for identity / multi-chain
    ton_address = Column(String, nullable=True)

    # Optional SLH-specific column – we keep it for compatibility and
    # always mirror bnb_address into it so the DB schema stays in sync.
    slh_address = Column(String, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )


class Transaction(Base):
    """טבלת לוג של העברות SLH (פנימיות + on-chain).

    from_telegram_id / to_telegram_id:
        מזהים של משתמשים בקהילה (יכולים להיות None כאשר המערכת מחלקת בונוס).
    onchain:
        True אם בוצעה גם תנועה על גבי הבלוקצ'יין (BSC / TON).
    tx_hash:
        מזהה טרנזקציה על הרשת (אם יש).
    """
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    from_telegram_id = Column(String, ForeignKey("wallets.telegram_id"), nullable=True)
    to_telegram_id = Column(String, ForeignKey("wallets.telegram_id"), nullable=True)

    amount = Column(Numeric(precision=40, scale=18), nullable=False)
    currency = Column(String, nullable=False, default="SLH")
    chain = Column(String, nullable=False, default="INTERNAL")  # INTERNAL / BSC / TON
    onchain = Column(Boolean, nullable=False, default=False)

    tx_hash = Column(String, nullable=True)
    note = Column(String, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
