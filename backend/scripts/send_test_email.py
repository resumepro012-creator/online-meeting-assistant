"""Send one real verification-style email through the configured SMTP server.

Nothing is mocked and nothing is stored: the message goes through the exact same
function the registration flow uses (`send_verification_code`), so a success here
means the account-verification email can really be delivered.

Usage (from `backend/`):

    .\\.venv\\Scripts\\python.exe scripts\\send_test_email.py you@uog.edu.pk

Exit codes:
    0 -> the SMTP server accepted the message
    2 -> EMAIL_BACKEND is not 'smtp', so nothing would be delivered
    3 -> the send failed (the SMTP error is printed)

Credentials are never read from this file — they come from the environment or the
git-ignored `backend/.env`.
"""

from __future__ import annotations

import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app.core.config import settings  # noqa: E402
from app.core.email import EmailDeliveryError, send_verification_code  # noqa: E402
from app.core.security import generate_verification_code  # noqa: E402


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__)
        return 64

    to_email = argv[1]
    backend = settings.email_backend.strip().lower()

    print(f"EMAIL_BACKEND   = {backend}")
    print(f"SMTP_HOST       = {settings.smtp_host or '(not set)'}")
    print(f"SMTP_PORT       = {settings.smtp_port}")
    print(f"SMTP_USERNAME   = {settings.smtp_username or '(not set)'}")
    print(f"SMTP_USE_STARTTLS = {settings.smtp_use_starttls}")
    print(f"SMTP_FROM_EMAIL = {settings.smtp_from_email}")
    print(f"Sending to      = {to_email}")

    if backend != "smtp":
        print(
            "\nRefusing to run: EMAIL_BACKEND is not 'smtp', so no mail would be "
            "delivered. Set EMAIL_BACKEND=smtp together with the SMTP_* settings in "
            "backend/.env first."
        )
        return 2

    code = generate_verification_code()
    try:
        send_verification_code(to_email, code, "SMTP test")
    except EmailDeliveryError as exc:
        print(f"\nFAILED: {exc}")
        return 3

    print(f"\nOK: the SMTP server accepted the message. The code that was sent is {code}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
