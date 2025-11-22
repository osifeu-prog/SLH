from sqlalchemy import String, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


class Wallet(Base):
    __tablename__ = "wallets"

    telegram_id: Mapped[str] = mapped_column(String(32), primary_key=True, index=True)
    username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    first_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    last_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    bnb_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    ton_address: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
