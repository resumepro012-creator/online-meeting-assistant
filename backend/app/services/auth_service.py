"""Account creation, credential checks, institute-email verification and
password reset.

Policy in one place:
*   only institutional emails may register — any `.edu` / `.edu.<cc>` / `.ac.<cc>`
    address when `ACCEPT_ANY_ACADEMIC_DOMAIN` is on (the default), plus the
    domains explicitly listed in `UNIVERSITY_EMAIL_DOMAINS`; personal providers
    (gmail.com, outlook.com, ...) are always refused — see `is_allowed_email`;
*   a new account is created **inactive** and only becomes usable after the
    6-digit code that was emailed to it is confirmed;
*   verification codes and reset tokens are stored as PBKDF2 hashes, never in
    plain text.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import email as email_sender
from app.core.config import settings
from app.core.ids import new_id
from app.core.security import (
    generate_reset_token,
    generate_verification_code,
    hash_password,
    hash_secret,
    make_initials,
    verify_password,
    verify_secret,
)
from app.models import User


# --------------------------------------------------------------------------- #
# Errors — each maps to a distinct HTTP status/message in app/api/auth.py
# --------------------------------------------------------------------------- #
class EmailAlreadyRegistered(ValueError):
    pass


class EmailDomainNotAllowed(ValueError):
    def __init__(self, domain: str) -> None:
        self.domain = domain
        super().__init__(
            f"'{domain}' is not an institutional email domain. "
            "Please register with your institute email address."
        )


class VerificationCodeExpired(ValueError):
    pass


class InvalidVerificationCode(ValueError):
    pass


class TooManyVerificationAttempts(ValueError):
    pass


class ResendTooSoon(ValueError):
    def __init__(self, seconds_remaining: int) -> None:
        self.seconds_remaining = seconds_remaining
        super().__init__(
            f"Please wait {seconds_remaining} more second(s) before requesting another code."
        )


class InvalidResetToken(ValueError):
    pass


# --------------------------------------------------------------------------- #
# Institutional email policy
# --------------------------------------------------------------------------- #
# Academic/institutional domains end in `.edu` (including country forms such as
# `.edu.pk`, `.edu.au`) or `.ac.<cc>` (e.g. `.ac.uk`). The pattern is anchored to
# the end, so `someone@edu.gmail.com` is NOT treated as institutional.
_ACADEMIC_DOMAIN_PATTERN = re.compile(r"\.edu(\.[a-z]{2,3})?$|\.ac\.[a-z]{2,3}$")


def email_domain(address: str) -> str:
    return address.strip().lower().rsplit("@", 1)[-1]


def is_academic_email_domain(domain: str) -> bool:
    """True for institutional domains such as `uog.edu.pk` or `ox.ac.uk`."""
    return bool(_ACADEMIC_DOMAIN_PATTERN.search(domain.strip().lower()))


def is_allowed_email(address: str) -> bool:
    """True when the address may register / sign in.

    Two rules are accepted:
    *   the domain is one of the explicitly approved domains — an exact match or
        a subdomain of one (`cs.student.edu` matches an approved `student.edu`);
    *   or, when `ACCEPT_ANY_ACADEMIC_DOMAIN` is on (the default), the domain is
        an institutional one such as `uog.edu.pk`, `anything.edu` or `ox.ac.uk`.

    Personal providers (gmail.com, outlook.com, yahoo.com, ...) never match.
    """
    address = address.strip().lower()
    if "@" not in address:
        return False
    domain = email_domain(address)
    if not domain:
        return False
    if any(
        domain == allowed or domain.endswith(f".{allowed}")
        for allowed in settings.allowed_email_domains
    ):
        return True
    return settings.accept_any_academic_domain and is_academic_email_domain(domain)


# --------------------------------------------------------------------------- #
# Users
# --------------------------------------------------------------------------- #
def get_user_by_email(db: Session, email: str) -> User | None:
    return db.scalars(select(User).where(User.email == email.strip().lower())).first()


def create_user(
    db: Session,
    name: str,
    email: str,
    password: str,
    program: str | None = None,
    *,
    is_verified: bool = False,
) -> User:
    """Creates the account. Raises `EmailDomainNotAllowed` / `EmailAlreadyRegistered`.

    The account is inactive until `verify_email` succeeds, unless the caller
    explicitly asks for a pre-verified account (used by the test fixtures).
    """
    normalized = email.strip().lower()
    if not is_allowed_email(normalized):
        raise EmailDomainNotAllowed(email_domain(normalized))
    if get_user_by_email(db, normalized):
        raise EmailAlreadyRegistered("An account with this email already exists.")

    user = User(
        id=new_id("usr-"),
        name=name.strip(),
        email=normalized,
        password_hash=hash_password(password),
        avatar_initials=make_initials(name),
        program=program,
        is_verified=is_verified,
        token_version=0,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def authenticate(db: Session, email: str, password: str) -> User | None:
    """Checks the credentials only. Verification state is handled by the caller."""
    user = get_user_by_email(db, email)
    if user is None:
        # Verify against a dummy hash so timing does not reveal whether the
        # email exists.
        verify_password(password, hash_password("dummy-password"))
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user


# --------------------------------------------------------------------------- #
# Email verification
# --------------------------------------------------------------------------- #
def _now() -> datetime:
    return datetime.now(timezone.utc)


def _as_aware(value: datetime | None) -> datetime | None:
    """SQLite returns naive datetimes; compare them as UTC."""
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def issue_verification_code(db: Session, user: User) -> str:
    """Generates a fresh code, stores its hash, emails it, and returns the code.

    The plaintext code is returned so the API layer can echo it in console
    (development) mode only — see `Settings.exposes_verification_code`.
    """
    code = generate_verification_code()
    user.verification_code_hash = hash_secret(code)
    user.verification_code_expires_at = _now() + timedelta(
        minutes=settings.verification_code_ttl_minutes
    )
    user.verification_attempts = 0
    user.verification_last_sent_at = _now()
    db.commit()
    db.refresh(user)
    email_sender.send_verification_code(user.email, code, user.name)
    return code


def register_user(
    db: Session, name: str, email: str, password: str, program: str | None = None
) -> tuple[User, str]:
    """Creates an inactive account and sends the verification code."""
    user = create_user(db, name=name, email=email, password=password, program=program)
    code = issue_verification_code(db, user)
    return user, code


def verify_email(db: Session, email: str, code: str) -> User:
    """Activates the account when the code matches and has not expired."""
    user = get_user_by_email(db, email)
    if user is None:
        raise InvalidVerificationCode("No account found for that email address.")
    if user.is_verified:
        return user
    if not user.verification_code_hash:
        raise InvalidVerificationCode("No verification code is pending. Request a new one.")
    expires_at = _as_aware(user.verification_code_expires_at)
    if expires_at is None or expires_at < _now():
        raise VerificationCodeExpired("That code has expired. Request a new one.")
    if user.verification_attempts >= settings.verification_max_attempts:
        raise TooManyVerificationAttempts(
            "Too many incorrect attempts. Request a new verification code."
        )

    if not verify_secret(code.strip(), user.verification_code_hash):
        user.verification_attempts += 1
        db.commit()
        remaining = max(settings.verification_max_attempts - user.verification_attempts, 0)
        raise InvalidVerificationCode(
            f"That code is not correct. {remaining} attempt(s) remaining."
        )

    user.is_verified = True
    user.verification_code_hash = None
    user.verification_code_expires_at = None
    user.verification_attempts = 0
    db.commit()
    db.refresh(user)
    return user


def resend_verification(db: Session, email: str) -> tuple[bool, str | None]:
    """Sends a new code, subject to a cooldown. Returns (sent, plaintext code).

    Returns `(False, None)` for an unknown or already-verified address instead of
    an error, so the endpoint does not disclose which emails are registered.
    """
    user = get_user_by_email(db, email)
    if user is None or user.is_verified:
        return False, None

    last_sent = _as_aware(user.verification_last_sent_at)
    if last_sent is not None:
        elapsed = (_now() - last_sent).total_seconds()
        cooldown = settings.verification_resend_cooldown_seconds
        if elapsed < cooldown:
            raise ResendTooSoon(int(cooldown - elapsed) + 1)

    return True, issue_verification_code(db, user)


# --------------------------------------------------------------------------- #
# Password reset
# --------------------------------------------------------------------------- #
def issue_reset_token(db: Session, user: User) -> str:
    """Stores a hashed reset token and returns the plaintext token."""
    token = generate_reset_token()
    user.reset_token_hash = hash_secret(token)
    user.reset_token_expires_at = _now() + timedelta(minutes=settings.password_reset_ttl_minutes)
    db.commit()
    return token


def request_password_reset(db: Session, email: str) -> None:
    """Emails a reset link when the account exists. Never reveals the outcome."""
    user = get_user_by_email(db, email)
    if user is None:
        return
    token = issue_reset_token(db, user)
    link = f"{settings.public_app_url.rstrip('/')}/reset-password?token={token}"
    email_sender.send_password_reset(user.email, link, user.name)


def reset_password(db: Session, token: str, new_password: str) -> User:
    """Consumes a reset token, sets the new password and revokes existing tokens.

    The stored hash is salted, so the token cannot be looked up by value; instead
    the candidate token is checked against every account that currently has a
    live reset token. That set is tiny for this prototype and is bounded by
    `password_reset_ttl_minutes`.
    """
    candidate = token.strip()
    if not candidate:
        raise InvalidResetToken("This password-reset link is not valid.")

    now = _now()
    live = db.scalars(select(User).where(User.reset_token_expires_at.is_not(None))).all()
    matched: User | None = None
    for user in live:
        expires_at = _as_aware(user.reset_token_expires_at)
        if expires_at is None or expires_at < now:
            continue
        if verify_secret(candidate, user.reset_token_hash):
            matched = user
            break

    if matched is None:
        raise InvalidResetToken("This password-reset link is invalid or has expired.")

    matched.password_hash = hash_password(new_password)
    matched.reset_token_hash = None
    matched.reset_token_expires_at = None
    # Every token issued before the reset stops working immediately.
    matched.token_version += 1
    # A successful reset also proves control of the mailbox.
    matched.is_verified = True
    db.commit()
    db.refresh(matched)
    return matched
