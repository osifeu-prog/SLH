
from datetime import datetime
from sqlalchemy import Column, DateTime, String
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
