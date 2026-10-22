"""Database engine/session wiring.

SQLite by default (`sqlite:///./data/app.db`). The `data/` directory and tables
are created automatically on startup — see `app/db/init_db.py`.

Switching to PostgreSQL only requires changing DATABASE_URL; no model changes.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings

_is_sqlite = settings.database_url.startswith("sqlite")

if _is_sqlite:
    # Make sure the parent folder of the SQLite file exists before connecting.
    db_path = settings.database_url.split("sqlite:///")[-1]
    if db_path and db_path != ":memory:":
        Path(db_path).resolve().parent.mkdir(parents=True, exist_ok=True)

engine: Engine = create_engine(
    settings.database_url,
    # SQLite + FastAPI (multi-threaded) needs this flag; `timeout` makes
    # concurrent readers wait for the background-processing writer instead of
    # failing with "database is locked".
    connect_args={"check_same_thread": False, "timeout": 30} if _is_sqlite else {},
    future=True,
)

if _is_sqlite:

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, _connection_record):  # noqa: ANN001
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.close()


SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def get_db() -> Iterator[Session]:
    """FastAPI dependency that yields a session and always closes it."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
