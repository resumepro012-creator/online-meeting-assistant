"""Shared FastAPI dependencies (auth, current user)."""

from __future__ import annotations

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.db.session import get_db
from app.models import User

_bearer = HTTPBearer(auto_error=False, description="JWT access token from /api/auth/login")

_UNAUTHORIZED = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Not authenticated. Sign in and send the token as 'Authorization: Bearer <token>'.",
    headers={"WWW-Authenticate": "Bearer"},
)

_EMAIL_NOT_VERIFIED = HTTPException(
    status_code=status.HTTP_403_FORBIDDEN,
    detail="Your institute email address has not been verified yet.",
)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None or not credentials.credentials:
        raise _UNAUTHORIZED

    decoded = decode_access_token(credentials.credentials)
    if decoded is None:
        raise _UNAUTHORIZED
    user_id, token_version = decoded

    user = db.get(User, user_id)
    if user is None:
        raise _UNAUTHORIZED
    # A password reset bumps `token_version`, which revokes every token issued
    # before it — even if such a token has not expired yet.
    if token_version != user.token_version:
        raise _UNAUTHORIZED
    # Belt-and-braces: login already refuses unverified accounts, so a token
    # should not exist for one, but protected routes must not depend on that.
    if not user.is_verified:
        raise _EMAIL_NOT_VERIFIED
    return user
