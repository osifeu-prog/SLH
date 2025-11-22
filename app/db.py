from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

from .config import settings


# ---------------------------------------------------
# SQLAlchemy Base Class
# ---------------------------------------------------
class Base(DeclarativeBase):
    pass


# ---------------------------------------------------
# Engine – Railway PostgreSQL
# ---------------------------------------------------
# Railway נותנים connection string עם sslmode=require
DATABASE_URL = settings.database_url

engine = create_engine(
    DATABASE_URL,
    future=True,
    pool_pre_ping=True,         # Handles dropped / idle connections
    pool_size=5,
    max_overflow=10,
)


# ---------------------------------------------------
# Session Factory
# ---------------------------------------------------
SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
)


# ---------------------------------------------------
# Dependency: FastAPI get_db()
# ---------------------------------------------------
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ---------------------------------------------------
# init_db – Only for LOCAL usage, not for migrations
# ---------------------------------------------------
def init_db():
    """
    LOCAL ONLY:
    יצירת טבלאות אוטומטית למי שלא משתמש ב־Alembic.
    ב־Production אנחנו משתמשים Alembic.
    """
    from . import models  # noqa: F401 – ensures models are imported
    Base.metadata.create_all(bind=engine)
