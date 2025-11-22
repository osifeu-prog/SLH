from __future__ import annotations

from typing import Generator

from sqlalchemy.orm import Session

from .db import get_db


def get_db_session() -> Generator[Session, None, None]:
    yield from get_db()
