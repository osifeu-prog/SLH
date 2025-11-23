from datetime import datetime

from sqlalchemy import Column, DateTime, String
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class Wallet(Base):
    __tablename__ = "wallets"

    # מזהה טלגרם - primary key
    telegram_id = Column(String(64), primary_key=True, index=True)

    # פרטים בסיסיים מהבוט
    username = Column(String(255), nullable=True, index=True)
    first_name = Column(String(255), nullable=True)
    last_name = Column(String(255), nullable=True)

    # כתובת BNB / SLH (אותה כתובת משמשת לשני המטבעות)
    bnb_address = Column(String(255), nullable=True, index=True)

    # כתובת TON לאימות זהות
    ton_address = Column(String(255), nullable=True, index=True)

    # כתובת SLH נפרדת (לפי דרישות עתידיות)
    slh_address = Column(String(255), nullable=True, index=True)

    # חותמות זמן
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
