"""Outgoing email for verification codes and password-reset links.

Two delivery backends are supported, selected with `EMAIL_BACKEND`:

* ``console`` (default) — the full message is written to the application log.
  This is a development convenience so the verification / reset flows can be
  exercised end to end without an SMTP server. Because the message is in the
  log, `Settings.exposes_verification_code` is True only in this mode and only
  in that mode may the code be echoed back in an API response.
* ``smtp`` — a real message is handed to an SMTP server through the standard
  library ``smtplib``. Host, port, credentials and sender all come from settings
  (environment / ``.env``); **no credential is ever hard-coded in this file**.

To satisfy the "never claim it works until it is tested" rule, a real send is
attempted only when ``EMAIL_BACKEND=smtp`` is configured; failures raise
``EmailDeliveryError`` and are reported to the caller instead of being swallowed.
"""

from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage

from app.core.config import settings

logger = logging.getLogger(__name__)


class EmailDeliveryError(RuntimeError):
    """Raised when a real SMTP send fails, so the caller can report it honestly."""


def _build_message(
    to_email: str, subject: str, text_body: str, html_body: str | None = None
) -> EmailMessage:
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = f"{settings.smtp_from_name} <{settings.smtp_from_email}>"
    message["To"] = to_email
    message.set_content(text_body)
    if html_body:
        message.add_alternative(html_body, subtype="html")
    return message


def _dispatch(message: EmailMessage, *, describe: str) -> None:
    """Hand the message to the configured backend.

    Raises ``EmailDeliveryError`` when the send cannot be performed, so the API
    layer can surface a truthful error rather than pretending it succeeded.
    """
    backend = settings.email_backend.strip().lower()

    if backend == "console":
        # Development only: print the whole message so a developer can read the
        # code straight from the backend log. Never enable this in production.
        logger.warning(
            "[dev email] %s -> %s\n%s",
            message["Subject"],
            message["To"],
            message.get_content().strip(),
        )
        return

    if backend != "smtp":
        raise EmailDeliveryError(
            f"Unknown EMAIL_BACKEND '{settings.email_backend}'. Use 'console' or 'smtp'."
        )

    if not settings.smtp_host:
        raise EmailDeliveryError(
            "EMAIL_BACKEND is 'smtp' but SMTP_HOST is not configured. "
            "Set SMTP_HOST (and credentials) in the environment."
        )

    try:
        if settings.smtp_use_ssl:
            # Implicit TLS (SMTPS), typically port 465.
            client: smtplib.SMTP = smtplib.SMTP_SSL(
                settings.smtp_host,
                settings.smtp_port,
                timeout=settings.smtp_timeout_seconds,
            )
        else:
            client = smtplib.SMTP(
                settings.smtp_host, settings.smtp_port, timeout=settings.smtp_timeout_seconds
            )
        with client as server:
            if settings.smtp_use_starttls and not settings.smtp_use_ssl:
                server.starttls()
            if settings.smtp_username:
                server.login(settings.smtp_username, settings.smtp_password)
            server.send_message(message)
    except (OSError, smtplib.SMTPException) as exc:
        raise EmailDeliveryError(f"Could not send the {describe} email: {exc}") from exc


def send_verification_code(to_email: str, code: str, name: str = "") -> None:
    """Emails the 6-digit verification code for a new account."""
    minutes = settings.verification_code_ttl_minutes
    greeting = f"Hi {name}," if name else "Hi,"
    text_body = (
        f"{greeting}\n\n"
        "Your AI Online Class Assistant verification code is:\n\n"
        f"    {code}\n\n"
        f"It expires in {minutes} minutes. If you did not request this, you can "
        "safely ignore this email.\n"
    )
    message = _build_message(to_email, "Your institute email verification code", text_body)
    _dispatch(message, describe="verification")


def send_password_reset(to_email: str, reset_url: str, name: str = "") -> None:
    """Emails the password-reset link. The link is built from PUBLIC_APP_URL."""
    minutes = settings.password_reset_ttl_minutes
    greeting = f"Hi {name}," if name else "Hi,"
    text_body = (
        f"{greeting}\n\n"
        "We received a request to reset your AI Online Class Assistant password. "
        "Open the link below to choose a new one:\n\n"
        f"    {reset_url}\n\n"
        f"The link expires in {minutes} minutes. If you did not request this, you "
        "can safely ignore this email — your password will not change.\n"
    )
    message = _build_message(to_email, "Reset your AI Online Class Assistant password", text_body)
    _dispatch(message, describe="password-reset")
