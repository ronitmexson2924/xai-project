"""The per-request database session dependency (shared by auth and the API routers, so one
request uses one session)."""

from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from app.db.session import SessionLocal


def get_session() -> Iterator[Session]:
    with SessionLocal() as session:
        yield session


DbSession = Annotated[Session, Depends(get_session)]
