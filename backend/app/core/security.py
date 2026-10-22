"""Password hashing, one-time-code helpers and JWT handling.

Password hashing uses PBKDF2-HMAC-SHA256 (260k iterations, 16-byte random salt
per user) from the standard library. This is an established, recommended
practice (NIST SP 800-63B) and avoids pulling in a binary dependency such as
bcrypt on Windows. Passwords are never stored or logged in plain text.

The same primitive is reused to store email-verification codes and password-reset
tokens as *hashes* rather than plain values, so a database read does not reveal a
code that could still be used.

Token format: standard JWT (HS256) with `sub` = user id, `ver` = the user's
`token_version`, and an `exp` claim. The secret comes from settings/env, never
from source code. Bumping `User.token_version` (done on password reset)
immediately invalidates every token that was issued earlier.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

import jwt
from jwt.exceptions import InvalidTokenError

from app.core.config import settings

_ALGORITHM = "pbkdf2_sha256"
_ITERATIONS = 260_000
_SALT_BYTES = 16

# A 6-digit code is compared in constant time; the value space is small, so the
# attempt counter (see auth_service) is what actually protects it. Public so the
# API can report the expected length to the frontend.
OTP_DIGITS = 6


def hash_secret(value: str) -> str:
    """Returns a self-describing hash string: algo$iterations$salt$hash."""
    salt = secrets.token_bytes(_SALT_BYTES)
    digest = hashlib.pbkdf2_hmac("sha256", value.encode("utf-8"), salt, _ITERATIONS)
    return "$".join(
        [
            _ALGORITHM,
            str(_ITERATIONS),
            base64.b64encode(salt).decode("ascii"),
            base64.b64encode(digest).decode("ascii"),
        ]
    )


def verify_secret(value: str, stored: str | None) -> bool:
    if not stored:
        return False
    try:
        algo, iterations, salt_b64, digest_b64 = stored.split("$")
        if algo != _ALGORITHM:
            return False
        salt = base64.b64decode(salt_b64)
        expected = base64.b64decode(digest_b64)
        actual = hashlib.pbkdf2_hmac("sha256", value.encode("utf-8"), salt, int(iterations))
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


# Password hashing is the same primitive; these names keep the call sites readable.
def hash_password(password: str) -> str:
    return hash_secret(password)


def verify_password(password: str, stored: str) -> bool:
    return verify_secret(password, stored)


def generate_verification_code() -> str:
    """A random 6-digit code, using `secrets` so it is not predictable.

    `randbelow` is used instead of `random`/`randint` to keep this on the
    cryptographically secure path.
    """
    return "".join(str(secrets.randbelow(10)) for _ in range(OTP_DIGITS))


def generate_reset_token() -> str:
    """High-entropy token for the password-reset link."""
    return secrets.token_urlsafe(32)


def create_access_token(user_id: str, token_version: int = 0) -> tuple[str, int]:
    """Returns (token, expires_in_seconds)."""
    expires_delta = timedelta(minutes=settings.access_token_expire_minutes)
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "ver": token_version,
        "iat": int(now.timestamp()),
        "exp": int((now + expires_delta).timestamp()),
    }
    token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    return token, int(expires_delta.total_seconds())


def decode_access_token(token: str) -> tuple[str, int] | None:
    """Returns (user id, token version) from a token, or None when it is invalid."""
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except InvalidTokenError:
        return None
    subject = payload.get("sub")
    if not isinstance(subject, str):
        return None
    version = payload.get("ver", 0)
    return subject, version if isinstance(version, int) else 0


def make_initials(name: str) -> str:
    parts = [p for p in name.strip().split(" ") if p]
    initials = "".join(p[0] for p in parts[:2]).upper()
    return initials or "ST"
