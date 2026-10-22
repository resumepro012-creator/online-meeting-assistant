"""Live-HTTP smoke check.

Boots the real FastAPI app on a real socket (uvicorn in a background thread),
then exercises it over HTTP exactly the way the browser will. This is the
"does the server actually start and answer requests" check — the pytest suite
uses an in-process ASGI transport and therefore never binds a port.

Run:
    .venv\\Scripts\\python.exe scripts\\smoke_check.py
    .venv\\Scripts\\python.exe scripts\\smoke_check.py --base-url http://localhost:5173

The second form runs the identical report against an already-running stack, which
is how you verify the browser's real path (Vite dev server -> FastAPI).

It exercises the university-email requirement too: a personal (gmail) address is
refused, registration returns no token, an unverified account cannot log in, the
emailed code activates the account, and `/api/meetings/policy` reports that no
meeting is joined for you.

Requires the backend to be configured with an approved university domain and
`EMAIL_BACKEND=console` (the defaults in `backend/.env.example`). The domain is
read from `GET /api/auth/policy`, so nothing is hardcoded here — but without the
console backend the script cannot obtain the verification code and will say so.

Everything it prints is real output from the running server; nothing is faked.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import threading
import time
from pathlib import Path

import httpx
import uvicorn

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app.main import app  # noqa: E402

# The point of this script is the report below, not pip's/httpx's request log.
logging.getLogger("httpx").setLevel(logging.WARNING)

HOST = "127.0.0.1"
PORT = 8099
BASE = f"http://{HOST}:{PORT}"


class _Server(uvicorn.Server):
    def install_signal_handlers(self) -> None:  # not allowed off the main thread
        pass


def main() -> int:
    parser = argparse.ArgumentParser(description="Live-HTTP smoke check for the API.")
    parser.add_argument(
        "--base-url",
        default=None,
        help=(
            "Run against an already-running server instead of booting one in-process. "
            "Use http://localhost:5173 to test the browser's path through the Vite proxy."
        ),
    )
    args = parser.parse_args()

    server = None
    thread = None
    base = args.base_url or BASE

    if args.base_url is None:
        config = uvicorn.Config(app, host=HOST, port=PORT, log_level="warning")
        server = _Server(config)
        thread = threading.Thread(target=server.run, daemon=True)
        thread.start()

        deadline = time.time() + 30
        while not server.started and time.time() < deadline:
            time.sleep(0.2)
        if not server.started:
            print("FAIL: the server did not start within 30s")
            return 1
    else:
        print(f"target: {base} (existing server)")

    failures = 0
    try:
        with httpx.Client(base_url=base, timeout=15) as client:
            health = client.get("/api/health")
            print(f"GET /api/health           -> {health.status_code}")
            if health.status_code == 200:
                print("  " + json.dumps(health.json(), indent=2)[:900])
            else:
                failures += 1

            if args.base_url is None:
                # Swagger/OpenAPI live on the backend itself; a dev proxy only
                # forwards `/api`, so these two checks are skipped in that mode.
                docs = client.get("/docs")
                print(f"GET /docs (Swagger UI)    -> {docs.status_code}")
                failures += docs.status_code != 200

                schema = client.get("/openapi.json")
                route_count = (
                    len(schema.json().get("paths", {})) if schema.status_code == 200 else 0
                )
                print(f"GET /openapi.json         -> {schema.status_code} ({route_count} paths)")
                failures += schema.status_code != 200

            unauth = client.get("/api/classes")
            print(f"GET /api/classes (no token) -> {unauth.status_code} (401 expected)")
            failures += unauth.status_code != 401

            # --- university-email policy: the sad paths first --------------- #
            policy = client.get("/api/auth/policy")
            domains = policy.json().get("allowedEmailDomains") if policy.status_code == 200 else None
            print(f"GET  /api/auth/policy     -> {policy.status_code} (domains={domains})")
            failures += policy.status_code != 200

            # Use whatever domain the backend actually approves, so this script
            # does not hardcode the university's domain.
            approved = policy.json().get("allowedEmailDomains") or [] if policy.status_code == 200 else []
            university_domain = approved[0] if approved else "student.edu"

            personal = client.post(
                "/api/auth/register",
                json={
                    "name": "Personal Email",
                    "email": f"someone.personal.{int(time.time())}@gmail.com",
                    "password": "smoketest123",
                },
            )
            print(f"POST /api/auth/register (gmail) -> {personal.status_code} (400 expected)")
            failures += personal.status_code != 400

            # Signing in with a personal address is a different route, and it is
            # the one that drives the UI's "Please login with institute mail."
            personal_login = client.post(
                "/api/auth/login",
                json={"email": "someone.personal@gmail.com", "password": "smoketest123"},
            )
            print(f"POST /api/auth/login (gmail)    -> {personal_login.status_code} (403 expected)")
            failures += personal_login.status_code != 403
            failures += (
                personal_login.json().get("detail", {}).get("code") != "email_domain_not_allowed"
            )

            email = f"smoke.{int(time.time())}@{university_domain}"
            register = client.post(
                "/api/auth/register",
                json={"name": "Smoke Test", "email": email, "password": "smoketest123"},
            )
            print(f"POST /api/auth/register   -> {register.status_code} (201 expected, no token)")
            failures += register.status_code != 201

            token = None
            if register.status_code == 201:
                # Registering must NOT return a session: the account is inactive
                # until the emailed code is confirmed.
                failures += "accessToken" in register.json()
                print(f"  accessToken in register response: {'accessToken' in register.json()} "
                      f"(False expected)")

                early = client.post(
                    "/api/auth/login", json={"email": email, "password": "smoketest123"}
                )
                print(f"POST /api/auth/login (unverified) -> {early.status_code} (403 expected)")
                failures += early.status_code != 403

                code = register.json().get("devVerificationCode")
                if not code:
                    print(
                        "  NOTE: no devVerificationCode — EMAIL_BACKEND is not 'console', so the "
                        "code is in a real inbox and this script cannot continue."
                    )
                    failures += 1
                else:
                    verified = client.post(
                        "/api/auth/verify-email", json={"email": email, "code": code}
                    )
                    print(f"POST /api/auth/verify-email -> {verified.status_code} (activates account)")
                    failures += verified.status_code != 200
                    if verified.status_code == 200:
                        token = verified.json()["accessToken"]

            if token:
                auth = {"Authorization": f"Bearer {token}"}

                me = client.get("/api/auth/me", headers=auth)
                print(f"GET /api/auth/me          -> {me.status_code} ({me.json().get('email')})")
                failures += me.status_code != 200

                # Application sign-in is not authorization to join a meeting.
                meeting = client.get(
                    "/api/meetings/policy",
                    params={"link": "https://meet.google.com/abc-defg-hij"},
                    headers=auth,
                )
                meeting_body = meeting.json() if meeting.status_code == 200 else {}
                print(
                    f"GET /api/meetings/policy  -> {meeting.status_code} "
                    f"({meeting_body.get('platformName')}, "
                    f"automatedJoinSupported={meeting_body.get('automatedJoinSupported')})"
                )
                failures += meeting.status_code != 200
                failures += meeting_body.get("automatedJoinSupported") is not False

                course = client.post(
                    "/api/classes",
                    json={"title": "Smoke Lecture", "subject": "Deep Learning"},
                    headers=auth,
                )
                print(f"POST /api/classes         -> {course.status_code}")
                failures += course.status_code != 201

                if course.status_code == 201:
                    course_id = course.json()["id"]
                    sample = BACKEND_DIR / "tests" / "data" / "sample_lecture.vtt"
                    with sample.open("rb") as handle:
                        uploaded = client.post(
                            "/api/lectures",
                            data={"courseId": course_id},
                            files={"file": (sample.name, handle, "text/vtt")},
                            headers=auth,
                        )
                    print(f"POST /api/lectures        -> {uploaded.status_code}")
                    failures += uploaded.status_code != 201

                    if uploaded.status_code == 201:
                        lecture_id = uploaded.json()["lecture"]["id"]

                        # A real server returns before the background job finishes,
                        # so poll the status endpoint the way the Processing page will.
                        status = None
                        poll_deadline = time.time() + 120
                        while time.time() < poll_deadline:
                            status = client.get(
                                f"/api/lectures/{lecture_id}/status", headers=auth
                            )
                            if status.status_code != 200:
                                break
                            if status.json()["status"] in {"completed", "failed"}:
                                break
                            time.sleep(0.5)

                        results = client.get(f"/api/lectures/{lecture_id}/results", headers=auth)
                        body = results.json() if results.status_code == 200 else {}
                        print(f"GET  .../{lecture_id}/status  -> {status.status_code} "
                              f"({status.json().get('status')}, {status.json().get('progress')}%)")
                        print(f"GET  .../{lecture_id}/results -> {results.status_code} "
                              f"(segments={body.get('pipeline', {}).get('segmentCount')}, "
                              f"announcements={len(body.get('announcements', []))}, "
                              f"questions={len(body.get('questions', []))}, "
                              f"actionItems={len(body.get('actionItems', []))})")
                        print(f"  note generated: {body.get('note') is not None}  "
                              f"classifier: {body.get('pipeline', {}).get('classifierMethod')}  "
                              f"stt: {body.get('pipeline', {}).get('sttMethod')}")
                        failures += status.status_code != 200
                        failures += status.json().get("status") != "completed"
                        failures += results.status_code != 200
                        failures += body.get("note") is None

                        # --- everything the React pages actually call ---------- #
                        # Phase 9 wired `src/services/api.ts` to exactly these
                        # routes, so the smoke check covers the browser's surface.
                        page_calls = [
                            ("GET", "/api/classes"),
                            ("GET", f"/api/classes/{course_id}"),
                            ("GET", f"/api/classes/{course_id}/lectures"),
                            ("GET", f"/api/classes/{course_id}/results"),
                            ("GET", f"/api/classes/{course_id}/notes"),
                            ("GET", f"/api/classes/{course_id}/announcements"),
                            ("GET", "/api/notes"),
                            ("GET", "/api/announcements"),
                            ("GET", "/api/dashboard/summary"),
                            ("GET", "/api/dashboard/recent-classes?limit=3"),
                            ("GET", f"/api/lectures/{lecture_id}/transcript"),
                            ("POST", f"/api/lectures/{lecture_id}/process"),
                        ]
                        print("frontend-facing endpoints:")
                        for method, path in page_calls:
                            response = client.request(method, path, headers=auth)
                            ok = response.status_code in {200, 201}
                            failures += not ok
                            print(
                                f"  {method:<4} {path:<52} -> {response.status_code}"
                                f"{'' if ok else '  <-- UNEXPECTED'}"
                            )
    finally:
        if server is not None and thread is not None:
            server.should_exit = True
            thread.join(timeout=10)

    print()
    print("SMOKE CHECK PASSED" if failures == 0 else f"SMOKE CHECK FAILED ({failures} problem(s))")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
