from sqlalchemy import Column, String, DateTime, func

from .db import Base


class Wallet(Base):
    __tablename__ = "wallets"

    telegram_id = Column(String, primary_key=True, index=True)
    username = Column(String, nullable=True)
    first_name = Column(String, nullable=True)
    last_name = Column(String, nullable=True)
    bnb_address = Column(String, nullable=True)
    slh_address = Column(String, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )
