"""Authentication behaviour: registration, login, token handling, hashing."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_health_reports_available_pipeline(client: TestClient) -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["database"] == "ok"
    # The test run forces the baseline classifier, and the endpoint must say so.
    assert body["pipeline"]["segmentClassifier"]["isRealModel"] is False
    assert body["pipeline"]["speechToText"]["available"] in (True, False)


def test_register_creates_an_inactive_account(client: TestClient) -> None:
    """Registration must NOT sign the user in — the university email comes first."""
    from uuid import uuid4

    email = f"pending.{uuid4().hex[:10]}@student.edu"
    response = client.post(
        "/api/auth/register",
        json={"name": "Pending Student", "email": email, "password": "testpass123"},
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["email"] == email
    assert body["verificationRequired"] is True
    assert body["devVerificationCode"]
    assert "accessToken" not in body

    # ...and the account cannot be used yet.
    blocked = client.post("/api/auth/login", json={"email": email, "password": "testpass123"})
    assert blocked.status_code == 403
    assert blocked.json()["detail"]["code"] == "email_not_verified"


def test_register_rejects_duplicate_email(client: TestClient, new_user: dict) -> None:
    again = client.post(
        "/api/auth/register",
        json={"name": "Someone Else", "email": new_user["email"], "password": "anotherpass1"},
    )
    assert again.status_code == 409


def test_register_validates_password_length(client: TestClient) -> None:
    response = client.post(
        "/api/auth/register",
        json={"name": "Short Pass", "email": "short.pass@student.edu", "password": "123"},
    )
    assert response.status_code == 422


def test_login_success_and_failure(client: TestClient, new_user: dict) -> None:
    ok = client.post(
        "/api/auth/login", json={"email": new_user["email"], "password": new_user["password"]}
    )
    assert ok.status_code == 200
    assert ok.json()["accessToken"]

    bad = client.post(
        "/api/auth/login", json={"email": new_user["email"], "password": "wrong-password"}
    )
    assert bad.status_code == 401

    unknown = client.post(
        "/api/auth/login", json={"email": "nobody@student.edu", "password": "whatever123"}
    )
    assert unknown.status_code == 401


def test_me_requires_valid_token(client: TestClient, new_user: dict) -> None:
    assert client.get("/api/auth/me").status_code == 401
    assert client.get("/api/auth/me", headers={"Authorization": "Bearer nonsense"}).status_code == 401

    me = client.get("/api/auth/me", headers=new_user["headers"])
    assert me.status_code == 200
    assert me.json()["email"] == new_user["email"]


def test_passwords_are_not_stored_in_plain_text(client: TestClient, new_user: dict) -> None:
    from sqlalchemy import select

    from app.db.session import SessionLocal
    from app.models import User

    with SessionLocal() as db:
        user = db.scalars(select(User).where(User.email == new_user["email"])).first()
    assert user is not None
    assert new_user["password"] not in user.password_hash
    assert user.password_hash.startswith("pbkdf2_sha256$")


def test_classes_are_scoped_to_the_owner(client: TestClient, new_user: dict) -> None:
    created = client.post(
        "/api/classes",
        json={"title": "Private Lecture", "subject": "Deep Learning"},
        headers=new_user["headers"],
    )
    assert created.status_code == 201
    course_id = created.json()["id"]

    # A different account must not be able to read it.
    from uuid import uuid4

    other_email = f"other.{uuid4().hex[:8]}@student.edu"
    registered = client.post(
        "/api/auth/register",
        json={"name": "Other Student", "email": other_email, "password": "otherpass123"},
    )
    assert registered.status_code == 201, registered.text
    other = client.post(
        "/api/auth/verify-email",
        json={"email": other_email, "code": registered.json()["devVerificationCode"]},
    )
    assert other.status_code == 200, other.text
    other_headers = {"Authorization": f"Bearer {other.json()['accessToken']}"}
    assert client.get(f"/api/classes/{course_id}", headers=other_headers).status_code == 404
    assert client.get("/api/classes", headers=other_headers).json() == []
