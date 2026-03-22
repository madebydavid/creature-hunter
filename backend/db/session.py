import os
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker


def _require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable {name}")
    return value


_engine = None
_SessionLocal = None


def get_db() -> Generator[Session, None, None]:
    # FastAPI dependency uses generator semantics to ensure the connection is closed.
    global _engine, _SessionLocal
    if _SessionLocal is None:
        url = _require_env("DATABASE_URL")
        # SQLAlchemy 2.x engine; `pool_pre_ping` avoids stale connections in Docker dev.
        _engine = create_engine(url, pool_pre_ping=True)
        _SessionLocal = sessionmaker(bind=_engine, autocommit=False, autoflush=False)

    SessionLocal = _SessionLocal
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

