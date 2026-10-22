"""Student account model."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    # PBKDF2 string, never the raw password. See app/core/security.py
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    avatar_initials: Mapped[str] = mapped_column(String(4), default="ST")
    program: Mapped[str | None] = mapped_column(String(120), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    # --- University email verification ---
    # An account stays inactive (is_verified=False) until the emailed code is
    # confirmed, so login is refused in the meantime. See app/services/auth_service.py
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # The verification code is stored as a PBKDF2 hash, never in plain text.
    verification_code_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    verification_code_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    verification_attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    verification_last_sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # --- Password reset ---
    reset_token_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    reset_token_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Bumped on password reset; every JWT carrying an older `ver` is then rejected.
    token_version: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    courses: Mapped[list["Course"]] = relationship(  # noqa: F821
        back_populates="user", cascade="all, delete-orphan"
    )
