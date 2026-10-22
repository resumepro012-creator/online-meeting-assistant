"""Database initialisation.

The project intentionally avoids a migration framework for the prototype: the
schema is created from the SQLAlchemy models on startup (`init_db`). The
procedure is documented in the project README. If the schema changes later
during development, delete `backend/data/app.db` and restart, or introduce
Alembic at that point.

Because `create_all` only creates *missing tables*, an existing SQLite file does
not automatically gain newly added columns. `_ensure_sqlite_columns` therefore
adds any that are missing, so an existing `data/app.db` keeps working instead of
having to be deleted.
"""

from __future__ import annotations

from app.core.config import settings
from app.db.base import Base
from app.db.session import engine
from app.models import *  # noqa: F401,F403  (ensures all models are registered)

# Columns introduced after the first release, per table. Each entry is
# (column name, SQLite column definition) and is applied only when absent.
_ADDED_COLUMNS: dict[str, list[tuple[str, str]]] = {
    "users": [
        ("is_verified", "BOOLEAN NOT NULL DEFAULT 0"),
        ("verification_code_hash", "VARCHAR(255)"),
        ("verification_code_expires_at", "DATETIME"),
        ("verification_attempts", "INTEGER NOT NULL DEFAULT 0"),
        ("verification_last_sent_at", "DATETIME"),
        ("reset_token_hash", "VARCHAR(255)"),
        ("reset_token_expires_at", "DATETIME"),
        ("token_version", "INTEGER NOT NULL DEFAULT 0"),
    ],
}


def _ensure_sqlite_columns() -> None:
    """Idempotently add the columns above to an existing SQLite database."""
    if not settings.database_url.startswith("sqlite"):
        return

    with engine.begin() as conn:
        for table, columns in _ADDED_COLUMNS.items():
            present = {
                row[1] for row in conn.exec_driver_sql(f'PRAGMA table_info("{table}")').fetchall()
            }
            if not present:
                continue  # table not created yet — create_all already handled it
            for name, ddl in columns:
                if name in present:
                    continue
                conn.exec_driver_sql(f'ALTER TABLE "{table}" ADD COLUMN {name} {ddl}')
                if table == "users" and name == "is_verified":
                    # Accounts that predate email verification are treated as
                    # already verified so this change cannot lock anyone out.
                    # Runs only once, when the column is first introduced.
                    conn.exec_driver_sql('UPDATE "users" SET is_verified = 1')


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
    _ensure_sqlite_columns()
