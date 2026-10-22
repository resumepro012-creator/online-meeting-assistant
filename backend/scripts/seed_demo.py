"""Seeds a demo account with ONE class whose content is genuinely produced by the pipeline.

Design choice, on purpose: this script does **not** insert fabricated notes,
announcements or questions into the database. It drives the real HTTP API
exactly as the browser does — register/login, create a class, upload
``tests/data/sample_lecture.vtt``, wait for the background job — so every note,
announcement, question and action item in the demo account is real output that
the pipeline extracted from that bundled transcript.

The demo class is therefore a demonstration of the pipeline working, not a mock
dashboard. The printed method strings state which implementations produced it.

Run (backend must already be running on port 8000 — see README section 3):
    .venv\\Scripts\\python.exe scripts\\seed_demo.py
    .venv\\Scripts\\python.exe scripts\\seed_demo.py --base-url http://localhost:5173
    .venv\\Scripts\\python.exe scripts\\seed_demo.py --email me@example.com --password secret1

Idempotent: logging in is tried first, so re-running reuses the existing account
and adds another class rather than failing.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import httpx

BACKEND_DIR = Path(__file__).resolve().parents[1]
SAMPLE_TRANSCRIPT = BACKEND_DIR / "tests" / "data" / "sample_lecture.vtt"

DEFAULT_EMAIL = "demo@example.com"
DEFAULT_PASSWORD = "demo1234"
POLL_INTERVAL_S = 1.0
POLL_TIMEOUT_S = 300


def _fail(message: str) -> int:
    print(f"FAIL: {message}")
    return 1


def _console_safe(text: str) -> str:
    """Backend job messages contain typographic characters (e.g. an ellipsis) that
    mojibake on a non-UTF-8 Windows console codepage. Server output itself is
    unchanged; only this script's echo is normalised."""
    return text.encode("ascii", "replace").decode("ascii")


def _authenticate(client: httpx.Client, email: str, password: str) -> str:
    """Logs in if possible, otherwise registers and verifies the account.

    Registration no longer returns a token: the account stays inactive until the
    emailed code is confirmed (see backend/app/api/auth.py). With the default
    development ``console`` email backend the API echoes the code back, so this
    script can complete the whole flow without a mail server. If a real SMTP
    backend is configured the code must be read from the university inbox.
    """
    print(f"account: {email}")

    login = client.post("/api/auth/login", json={"email": email, "password": password})
    if login.status_code == 200:
        print("  signed in with the existing account")
        return login.json()["accessToken"]

    code: str | None = None
    register = client.post(
        "/api/auth/register",
        json={"name": "Demo Student", "email": email, "password": password, "program": "Deep Learning"},
    )
    if register.status_code == 201:
        print("  created the demo account")
        code = register.json().get("devVerificationCode")
    elif register.status_code == 409:
        print("  account already exists but is not verified")
        resend = client.post("/api/auth/resend-verification", json={"email": email})
        if resend.status_code == 200:
            code = resend.json().get("devVerificationCode")
    else:
        raise httpx.HTTPStatusError(
            f"could not log in ({login.status_code}) or register ({register.status_code}): "
            f"{register.text[:300]}",
            request=register.request,
            response=register,
        )

    if not code:
        raise RuntimeError(
            "this account still needs email verification, but no development code was "
            "returned (EMAIL_BACKEND is not 'console'). Verify the address from the "
            "university inbox, then re-run this script."
        )

    verified = client.post("/api/auth/verify-email", json={"email": email, "code": code})
    if verified.status_code != 200:
        raise httpx.HTTPStatusError(
            f"email verification failed ({verified.status_code}): {verified.text[:300]}",
            request=verified.request,
            response=verified,
        )
    print("  verified the university email address")
    return verified.json()["accessToken"]


def _wait_for_job(client: httpx.Client, lecture_id: str, headers: dict) -> dict:
    """Polls the real job until it finishes, echoing the stage transitions."""
    deadline = time.time() + POLL_TIMEOUT_S
    last_stage = None
    while time.time() < deadline:
        job = client.get(f"/api/lectures/{lecture_id}/status", headers=headers).json()
        if job["stage"] != last_stage:
            last_stage = job["stage"]
            print(f"  [{job['progress']:>3}%] {job['stage']}: {_console_safe(job.get('message') or '')}")
        if job["status"] == "completed":
            return job
        if job["status"] == "failed":
            raise RuntimeError(job.get("error") or job.get("message") or "the job failed")
        time.sleep(POLL_INTERVAL_S)
    raise TimeoutError(f"the job did not finish within {POLL_TIMEOUT_S}s")


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed a demo account via the real API.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--email", default=DEFAULT_EMAIL)
    parser.add_argument("--password", default=DEFAULT_PASSWORD)
    parser.add_argument("--title", default="Introduction to CNNs and Sequence Models")
    parser.add_argument("--subject", default="Deep Learning")
    args = parser.parse_args()

    if not SAMPLE_TRANSCRIPT.exists():
        return _fail(f"sample transcript not found at {SAMPLE_TRANSCRIPT}")

    print(f"target: {args.base_url}")

    try:
        with httpx.Client(base_url=args.base_url, timeout=30) as client:
            try:
                health = client.get("/api/health")
                health.raise_for_status()
            except httpx.HTTPError as exc:
                return _fail(
                    f"could not reach the backend at {args.base_url} ({exc}). "
                    "Start it first — see README section 3."
                )

            pipeline = health.json().get("pipeline", {})
            print(
                "  pipeline: stt="
                f"{pipeline.get('speechToText', {}).get('backend')} "
                f"available={pipeline.get('speechToText', {}).get('available')}, "
                f"classifier={pipeline.get('segmentClassifier', {}).get('method')}"
            )

            token = _authenticate(client, args.email, args.password)
            headers = {"Authorization": f"Bearer {token}"}

            print(f"class  : {args.title!r} / {args.subject!r}")
            created = client.post(
                "/api/classes",
                json={"title": args.title, "subject": args.subject},
                headers=headers,
            )
            created.raise_for_status()
            course = created.json()

            print(f"upload : {SAMPLE_TRANSCRIPT.name} ({SAMPLE_TRANSCRIPT.stat().st_size} bytes)")
            with SAMPLE_TRANSCRIPT.open("rb") as handle:
                upload = client.post(
                    "/api/lectures",
                    data={"courseId": course["id"], "startProcessing": "true"},
                    files={"file": (SAMPLE_TRANSCRIPT.name, handle, "text/vtt")},
                    headers=headers,
                )
            upload.raise_for_status()
            lecture = upload.json()["lecture"]

            print(f"job    : {lecture['id']}")
            _wait_for_job(client, lecture["id"], headers)

            results = client.get(f"/api/lectures/{lecture['id']}/results", headers=headers)
            results.raise_for_status()
            payload = results.json()
            info = payload["pipeline"]

            print()
            print("=" * 72)
            print("DEMO SEEDED - counts below are real pipeline output from the transcript")
            print("=" * 72)
            print(f"classId            : {course['id']}")
            print(f"lectureId          : {lecture['id']}")
            print(f"transcript segments: {info['segmentCount']}")
            print(f"note generated     : {payload['note'] is not None}")
            print(f"announcements      : {len(payload['announcements'])}")
            print(f"questions          : {len(payload['questions'])}")
            print(f"action items       : {len(payload['actionItems'])}")
            print(f"stt method         : {info['sttMethod']}")
            print(f"classifier method  : {info['classifierMethod']}")
            print(f"summarizer method  : {info['summarizerMethod']}")
            print()
            print(f"sign in with       : {args.email} / {args.password}")
            print("then open          : " + args.base_url.rstrip("/").replace(":8000", ":5173") + "/dashboard")
    except httpx.HTTPError as exc:
        return _fail(f"HTTP error: {exc}")
    except (RuntimeError, TimeoutError) as exc:
        return _fail(f"processing did not complete: {exc}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
