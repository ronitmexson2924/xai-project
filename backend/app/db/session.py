from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings

engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    """FastAPI dependency: one session per request. Handlers commit explicitly; anything not
    committed (an error, a read-only request) is rolled back when the request ends."""
    with SessionLocal() as session:
        try:
            yield session
        finally:
            session.rollback()
