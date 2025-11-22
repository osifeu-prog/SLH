from __future__ import annotations

import datetime as dt

from sqlalchemy import Column, String, DateTime, Integer, Numeric, ForeignKey
from sqlalchemy.orm import relationship

from .db import Base


class Wallet(Base):
    __tablename__ = "wallets"

    telegram_id = Column(String(64), primary_key=True, index=True)
    username = Column(String(64), nullable=True, index=True)
    first_name = Column(String(64), nullable=True)
    last_name = Column(String(64), nullable=True)

    bnb_address = Column(String(64), nullable=True, index=True)
    slh_address = Column(String(64), nullable=True, index=True)
    slh_ton_address = Column(String(128), nullable=True, index=True)

    created_at = Column(DateTime(timezone=True), default=dt.datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        default=dt.datetime.utcnow,
        onupdate=dt.datetime.utcnow,
        nullable=False,
    )

    # relationships
    outgoing_transfers = relationship(
        "InternalTransfer",
        foreign_keys="InternalTransfer.from_telegram_id",
        back_populates="from_wallet",
    )
    incoming_transfers = relationship(
        "InternalTransfer",
        foreign_keys="InternalTransfer.to_telegram_id",
        back_populates="to_wallet",
    )


class InternalTransfer(Base):
    __tablename__ = "internal_transfers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    from_telegram_id = Column(String(64), ForeignKey("wallets.telegram_id"), nullable=False, index=True)
    to_telegram_id = Column(String(64), ForeignKey("wallets.telegram_id"), nullable=False, index=True)

    amount_slh = Column(Numeric(precision=24, scale=8), nullable=False)
    memo = Column(String(255), nullable=True)

    created_at = Column(DateTime(timezone=True), default=dt.datetime.utcnow, nullable=False)

    from_wallet = relationship("Wallet", foreign_keys=[from_telegram_id], back_populates="outgoing_transfers")
    to_wallet = relationship("Wallet", foreign_keys=[to_telegram_id], back_populates="incoming_transfers")
