"""University-email registration, verification, login gating and password reset.

The suite runs with `UNIVERSITY_EMAIL_DOMAINS=student.edu` and
`EMAIL_BACKEND=console` (see conftest.py), so the verification code is returned
by the API instead of having to be read from a real inbox.
"""

from __future__ import annotations

from datetime import timedelta
from uuid import uuid4

from fastapi.testclient import TestClient

from app.core.security import create_access_token
from app.db.session import SessionLocal
from app.models import utcnow
from app.services import auth_service


def _register(client: TestClient, email: str, password: str = "testpass123") -> dict:
    response = client.post(
        "/api/auth/register", json={"name": "Test Student", "email": email, "password": password}
    )
    assert response.status_code == 201, response.text
    return response.json()


def _register_and_verify(client: TestClient, email: str, password: str = "testpass123") -> dict:
    body = _register(client, email, password)
    verified = client.post(
        "/api/auth/verify-email", json={"email": email, "code": body["devVerificationCode"]}
    )
    assert verified.status_code == 200, verified.text
    return verified.json()


# --------------------------------------------------------------------------- #
# University email policy
# --------------------------------------------------------------------------- #
def test_policy_endpoint_reports_the_configured_domains(client: TestClient) -> None:
    response = client.get("/api/auth/policy")
    assert response.status_code == 200
    body = response.json()
    assert "student.edu" in body["universityEmailDomains"]
    assert "student.edu" in body["allowedEmailDomains"]
    assert body["acceptAnyAcademicDomain"] is True
    assert body["verificationRequired"] is True
    assert body["devCodeExposed"] is True  # console backend during tests


def test_registration_rejects_personal_email(client: TestClient) -> None:
    for email in ("someone@gmail.com", "someone@outlook.com", "someone@yahoo.co.uk"):
        response = client.post(
            "/api/auth/register",
            json={"name": "Personal", "email": email, "password": "testpass123"},
        )
        assert response.status_code == 400, response.text
        assert response.json()["detail"]["code"] == "email_domain_not_allowed"


def test_any_institutional_email_domain_is_accepted(client: TestClient) -> None:
    """Any `.edu` / `.edu.<cc>` / `.ac.<cc>` address may register, not just the
    domains explicitly listed in UNIVERSITY_EMAIL_DOMAINS."""
    for domain in ("uog.edu.pk", "mit.edu", "ox.ac.uk"):
        email = f"inst.{uuid4().hex[:8]}@{domain}"
        body = _register_and_verify(client, email)
        assert body["student"]["email"] == email


def test_login_with_personal_email_asks_for_institute_mail(client: TestClient) -> None:
    response = client.post(
        "/api/auth/login", json={"email": "someone@gmail.com", "password": "whatever123"}
    )
    assert response.status_code == 403
    detail = response.json()["detail"]
    assert detail["code"] == "email_domain_not_allowed"
    assert detail["message"] == "Please login with institute mail."


def test_subdomain_of_an_approved_domain_is_accepted(client: TestClient) -> None:
    body = _register_and_verify(client, f"cs.{uuid4().hex[:8]}@cs.student.edu")
    assert body["student"]["email"].endswith("@cs.student.edu")


# --------------------------------------------------------------------------- #
# Verification
# --------------------------------------------------------------------------- #
def test_unverified_account_cannot_use_protected_routes(client: TestClient) -> None:
    """Even a hand-minted token is refused while the email is unverified."""
    email = f"unverified.{uuid4().hex[:8]}@student.edu"
    with SessionLocal() as db:
        user = auth_service.create_user(db, name="Unverified", email=email, password="testpass123")
        user_id, token_version = user.id, user.token_version

    token, _ = create_access_token(user_id, token_version)
    response = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 403
    assert response.json()["detail"] == "Your institute email address has not been verified yet."


def test_wrong_verification_code_is_rejected(client: TestClient) -> None:
    email = f"wrongcode.{uuid4().hex[:8]}@student.edu"
    _register(client, email)

    response = client.post("/api/auth/verify-email", json={"email": email, "code": "000001"})
    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "invalid_code"


def test_verified_account_can_log_in_and_reach_protected_routes(client: TestClient) -> None:
    email = f"verified.{uuid4().hex[:8]}@student.edu"
    _register_and_verify(client, email, "testpass123")

    login = client.post("/api/auth/login", json={"email": email, "password": "testpass123"})
    assert login.status_code == 200, login.text
    token = login.json()["accessToken"]

    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["email"] == email


def test_resend_is_rate_limited(client: TestClient) -> None:
    email = f"cooldown.{uuid4().hex[:8]}@student.edu"
    _register(client, email)

    # Immediately after registration the cooldown is still running.
    blocked = client.post("/api/auth/resend-verification", json={"email": email})
    assert blocked.status_code == 429
    assert blocked.json()["detail"]["code"] == "resend_too_soon"


def test_resend_returns_a_fresh_code_after_the_cooldown(client: TestClient) -> None:
    email = f"resend.{uuid4().hex[:8]}@student.edu"
    _register(client, email)

    # Wind the last-sent timestamp back instead of sleeping in the test.
    with SessionLocal() as db:
        user = auth_service.get_user_by_email(db, email)
        assert user is not None
        user.verification_last_sent_at = utcnow() - timedelta(hours=1)
        db.commit()

    response = client.post("/api/auth/resend-verification", json={"email": email})
    assert response.status_code == 200, response.text
    code = response.json()["devVerificationCode"]
    assert code

    verified = client.post("/api/auth/verify-email", json={"email": email, "code": code})
    assert verified.status_code == 200, verified.text


def test_verification_code_is_stored_hashed_not_in_plain_text(client: TestClient) -> None:
    email = f"hashcheck.{uuid4().hex[:8]}@student.edu"
    body = _register(client, email)
    code = body["devVerificationCode"]

    with SessionLocal() as db:
        user = auth_service.get_user_by_email(db, email)
    assert user is not None
    assert user.verification_code_hash is not None
    assert code not in user.verification_code_hash
    assert user.verification_code_hash.startswith("pbkdf2_sha256$")


# --------------------------------------------------------------------------- #
# Password reset
# --------------------------------------------------------------------------- #
def test_forgot_password_does_not_reveal_unknown_accounts(client: TestClient) -> None:
    known_email = f"known.{uuid4().hex[:8]}@student.edu"
    _register_and_verify(client, known_email)

    unknown = client.post(
        "/api/auth/forgot-password", json={"email": f"nobody.{uuid4().hex[:8]}@student.edu"}
    )
    known = client.post("/api/auth/forgot-password", json={"email": known_email})
    # Same status and wording either way, so the endpoint cannot be used to
    # discover which addresses are registered.
    assert unknown.status_code == known.status_code == 200
    assert unknown.json() == known.json()


def test_password_reset_flow(client: TestClient) -> None:
    email = f"reset.{uuid4().hex[:8]}@student.edu"
    session = _register_and_verify(client, email, "oldpass123")
    old_headers = {"Authorization": f"Bearer {session['accessToken']}"}
    assert client.get("/api/auth/me", headers=old_headers).status_code == 200

    # The endpoint itself never returns the token, so obtain it the way the
    # service does and hand it to the API as the emailed link would.
    with SessionLocal() as db:
        user = auth_service.get_user_by_email(db, email)
        assert user is not None
        token = auth_service.issue_reset_token(db, user)

    reset = client.post(
        "/api/auth/reset-password", json={"token": token, "password": "newpass456"}
    )
    assert reset.status_code == 200, reset.text

    # The old password no longer works; the new one does.
    assert (
        client.post("/api/auth/login", json={"email": email, "password": "oldpass123"}).status_code
        == 401
    )
    assert (
        client.post("/api/auth/login", json={"email": email, "password": "newpass456"}).status_code
        == 200
    )

    # Tokens issued before the reset were revoked by the token_version bump.
    assert client.get("/api/auth/me", headers=old_headers).status_code == 401

    # A reset token is single-use.
    assert (
        client.post(
            "/api/auth/reset-password", json={"token": token, "password": "another789"}
        ).status_code
        == 400
    )


def test_password_reset_rejects_an_invalid_token(client: TestClient) -> None:
    response = client.post(
        "/api/auth/reset-password", json={"token": "not-a-real-token", "password": "whatever123"}
    )
    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "invalid_reset_token"


def test_reset_token_is_stored_hashed(client: TestClient) -> None:
    email = f"resettoken.{uuid4().hex[:8]}@student.edu"
    _register_and_verify(client, email)

    with SessionLocal() as db:
        user = auth_service.get_user_by_email(db, email)
        assert user is not None
        token = auth_service.issue_reset_token(db, user)
        stored = user.reset_token_hash

    assert stored is not None
    assert token not in stored
    assert stored.startswith("pbkdf2_sha256$")
