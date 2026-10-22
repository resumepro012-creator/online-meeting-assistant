"""Pytest configuration.

Environment variables are set BEFORE the app is imported so the tests use an
isolated SQLite file, a temp upload folder, and the deterministic baseline
implementations (no model downloads during tests).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

TEST_DB = BACKEND_DIR / "data" / "test_app.db"
TEST_UPLOADS = BACKEND_DIR / "data" / "test_uploads"
TEST_UPLOADS.mkdir(parents=True, exist_ok=True)
TEST_DB.parent.mkdir(parents=True, exist_ok=True)

os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB.as_posix()}"
os.environ["UPLOAD_DIR"] = str(TEST_UPLOADS)
os.environ["JWT_SECRET"] = "test-only-secret"
os.environ["STT_BACKEND"] = "baseline"
os.environ["SEGMENT_CLASSIFIER_BACKEND"] = "baseline"
os.environ["SUMMARIZER_BACKEND"] = "baseline"
os.environ["LOG_LEVEL"] = "WARNING"
# University-email policy under test, and the development email backend so the
# verification code is returned by the API instead of having to be emailed.
os.environ["UNIVERSITY_EMAIL_DOMAINS"] = "student.edu"
os.environ["EMAIL_BACKEND"] = "console"

# Start each test session from a clean database.
for stale in (TEST_DB, TEST_DB.with_suffix(".db-wal"), TEST_DB.with_suffix(".db-shm")):
    stale.unlink(missing_ok=True)

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

DATA_DIR = Path(__file__).parent / "data"


@pytest.fixture(scope="session")
def client():
    # `with` triggers the lifespan hook, which creates the schema.
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def new_user(client: TestClient) -> dict:
    """Registers **and verifies** a fresh account, returning {headers, student}.

    Registration alone is no longer enough to obtain a token — the university
    email has to be confirmed first (see app/api/auth.py), so this fixture walks
    the real two-step flow.
    """
    from uuid import uuid4

    email = f"student.{uuid4().hex[:10]}@student.edu"
    password = "testpass123"

    registered = client.post(
        "/api/auth/register",
        json={"name": "Test Student", "email": email, "password": password},
    )
    assert registered.status_code == 201, registered.text
    code = registered.json()["devVerificationCode"]
    assert code, "tests run with EMAIL_BACKEND=console, so the code must be returned"

    verified = client.post("/api/auth/verify-email", json={"email": email, "code": code})
    assert verified.status_code == 200, verified.text
    body = verified.json()

    return {
        "email": email,
        "password": password,
        "student": body["student"],
        "headers": {"Authorization": f"Bearer {body['accessToken']}"},
    }


@pytest.fixture
def sample_lecture_path() -> Path:
    return DATA_DIR / "sample_lecture.vtt"
