
from sqlalchemy import Boolean, Column, DateTime, String, Integer, Numeric
from sqlalchemy.sql import func

from .db import Base


class Wallet(Base):
    __tablename__ = "wallets"

    telegram_id = Column(String, primary_key=True, index=True)
    bnb_address = Column(String, index=True, nullable=True)
    ton_address = Column(String, nullable=True)
    slh_address = Column(String, nullable=True)
    username = Column(String, nullable=True)
    first_name = Column(String, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, index=True)
    from_telegram_id = Column(String, index=True, nullable=True)
    to_telegram_id = Column(String, index=True, nullable=True)
    amount = Column(Numeric(40, 18), nullable=False)
    currency = Column(String, default="SLH", nullable=False)
    chain = Column(String, default="INTERNAL", nullable=False)
    tx_hash = Column(String, nullable=True)
    is_internal = Column(Boolean, default=True, nullable=False)
    note = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
