from sqlalchemy import Column, String, DateTime, func
from .db import Base


class Wallet(Base):
    __tablename__ = "wallets"

    telegram_id = Column(String(64), primary_key=True, index=True)
    username = Column(String(255), nullable=True)
    first_name = Column(String(255), nullable=True)
    bnb_address = Column(String(255), nullable=True)
    slh_address = Column(String(255), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )