"""End-to-end test: upload a lecture file -> process -> read the generated outputs.

This is the test that backs the claim "the backend works end to end without any
model download". It uses the deterministic baseline implementations configured in
``conftest.py`` (no Whisper, no Transformer), so it can run on any laptop.
"""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

ALLOWED_CATEGORIES = {
    "Assignment",
    "Quiz",
    "Exam",
    "Deadline",
    "Schedule Change",
    "General Announcement",
}
ALLOWED_SEGMENT_LABELS = {"QUESTION", "INFORMATION", "DISCUSSION", "DECISION", "ACTION_ITEM"}


def _create_class(client: TestClient, headers: dict, title: str = "CNN Lecture") -> dict:
    response = client.post(
        "/api/classes",
        json={"title": title, "subject": "Deep Learning"},
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return response.json()


def _upload(client: TestClient, headers: dict, course_id: str, path: Path) -> dict:
    """POSTs the sample transcript; background processing runs before this returns."""
    with path.open("rb") as handle:
        response = client.post(
            "/api/lectures",
            data={"courseId": course_id},
            files={"file": (path.name, handle, "text/vtt")},
            headers=headers,
        )
    assert response.status_code == 201, response.text
    return response.json()


def test_transcript_upload_runs_the_full_pipeline(
    client: TestClient, new_user: dict, sample_lecture_path: Path
) -> None:
    headers = new_user["headers"]
    course = _create_class(client, headers)
    created = _upload(client, headers, course["id"], sample_lecture_path)

    lecture = created["lecture"]
    assert lecture["sourceType"] == "upload_transcript"
    assert lecture["originalFilename"] == "sample_lecture.vtt"

    # --- job finished ------------------------------------------------------- #
    status_response = client.get(f"/api/lectures/{lecture['id']}/status", headers=headers)
    assert status_response.status_code == 200, status_response.text
    job = status_response.json()
    assert job["status"] == "completed", job
    assert job["progress"] == 100, job
    assert job["error"] is None, job
    assert {stage["key"] for stage in job["stages"]} >= {"preparing", "transcribing", "analyzing"}

    # --- transcript was parsed with real timestamps ------------------------- #
    transcript = client.get(f"/api/lectures/{lecture['id']}/transcript", headers=headers)
    assert transcript.status_code == 200, transcript.text
    segments = transcript.json()
    assert len(segments) >= 30, f"expected the whole VTT to be stored, got {len(segments)}"
    assert segments[0]["startSeconds"] == 1.0
    assert segments[0]["endSeconds"] == 6.5
    assert segments[0]["speaker"] == "Instructor"
    assert all(segment["category"] in ALLOWED_SEGMENT_LABELS for segment in segments)

    # --- results are labelled with the implementation that produced them ---- #
    results = client.get(f"/api/lectures/{lecture['id']}/results", headers=headers)
    assert results.status_code == 200, results.text
    body = results.json()
    pipeline = body["pipeline"]
    assert pipeline["sttMethod"] == "transcript-parser"
    assert pipeline["classifierMethod"] == "baseline-pattern-v1"
    assert pipeline["summarizerMethod"] == "extractive-textrank-lite-v1"
    assert pipeline["segmentCount"] == len(segments)

    # --- note ---------------------------------------------------------------- #
    note = body["note"]
    assert note is not None, "processing completed but no note was generated"
    assert note["classId"] == course["id"]
    assert note["summary"].strip(), "summary must not be empty"
    assert note["topics"], "notes must contain topic keywords"
    assert note["sections"], "notes must contain structured sections"

    # The summary must be grounded in the transcript, never invented.
    transcript_text = " ".join(segment["text"] for segment in segments)
    assert note["summary"].split(".")[0][:40] in transcript_text

    # --- questions ----------------------------------------------------------- #
    questions = body["questions"]
    asked = [question["text"] for question in questions]
    assert any("kernel" in text for text in asked), asked
    assert not any(
        text.lower().startswith("are there any questions") for text in asked
    ), "room-addressing meta questions must be filtered out"
    assert all(question["isAiGenerated"] is False for question in questions)

    # --- announcements ------------------------------------------------------- #
    announcements = body["announcements"]
    assert len(announcements) >= 3, announcements
    assert {item["category"] for item in announcements} <= ALLOWED_CATEGORIES
    assert any(item["category"] == "Assignment" for item in announcements), announcements
    assert any(item["category"] == "Exam" for item in announcements), announcements
    assert all(item["relatedClassId"] == course["id"] for item in announcements)
    assert all(item["relatedLecture"] for item in announcements)

    # --- action items + deadlines -------------------------------------------- #
    action_items = body["actionItems"]
    assert action_items, "the transcript contains an explicit assignment deadline"
    dated = [item for item in action_items if item["dueAt"]]
    assert dated, f"expected the 'September 23' deadline to be resolved, got {action_items}"
    assert all(item["dueAt"] is None or item["dueUncertain"] is False for item in action_items)
    assert any(item["assignee"] for item in action_items), action_items


def test_results_persist_and_reload_after_the_job_finished(
    client: TestClient, new_user: dict, sample_lecture_path: Path
) -> None:
    headers = new_user["headers"]
    course = _create_class(client, headers, title="Persistence Check")
    created = _upload(client, headers, course["id"], sample_lecture_path)
    lecture_id = created["lecture"]["id"]

    first = client.get(f"/api/lectures/{lecture_id}/results", headers=headers).json()
    second = client.get(f"/api/lectures/{lecture_id}/results", headers=headers).json()

    # A page refresh must not wipe or regenerate the outputs.
    assert first["note"]["id"] == second["note"]["id"]
    assert [item["id"] for item in first["announcements"]] == [
        item["id"] for item in second["announcements"]
    ]

    # The class now shows up as completed with notes in the sidebar/history.
    refreshed = client.get(f"/api/classes/{course['id']}", headers=headers)
    assert refreshed.status_code == 200, refreshed.text
    assert refreshed.json()["status"] == "completed"
    assert refreshed.json()["hasNotes"] is True

    summary = client.get("/api/dashboard/summary", headers=headers).json()
    assert summary["totalClasses"] >= 1
    assert summary["notesGenerated"] >= 1

    inbox = client.get("/api/announcements", headers=headers)
    assert inbox.status_code == 200, inbox.text
    assert len(inbox.json()) >= 3


def test_reprocessing_replaces_previous_outputs(
    client: TestClient, new_user: dict, sample_lecture_path: Path
) -> None:
    headers = new_user["headers"]
    course = _create_class(client, headers, title="Reprocess Check")
    created = _upload(client, headers, course["id"], sample_lecture_path)
    lecture_id = created["lecture"]["id"]

    before = client.get(f"/api/lectures/{lecture_id}/results", headers=headers).json()
    rerun = client.post(f"/api/lectures/{lecture_id}/process", headers=headers)
    assert rerun.status_code == 200, rerun.text
    after = client.get(f"/api/lectures/{lecture_id}/results", headers=headers).json()

    assert len(after["announcements"]) == len(before["announcements"])
    assert len(after["questions"]) == len(before["questions"])
    assert after["pipeline"]["segmentCount"] == before["pipeline"]["segmentCount"]
    # New rows are written, but the old ones must not survive alongside them.
    assert after["note"]["id"] != before["note"]["id"]


def test_other_students_cannot_read_a_lecture(
    client: TestClient, new_user: dict, sample_lecture_path: Path
) -> None:
    owner = new_user["headers"]
    course = _create_class(client, owner, title="Private Recording")
    created = _upload(client, owner, course["id"], sample_lecture_path)
    lecture_id = created["lecture"]["id"]

    intruder = client.post(
        "/api/auth/register",
        json={"name": "Other Student", "email": "intruder@student.edu", "password": "testpass123"},
    )
    assert intruder.status_code == 201, intruder.text
    # Registration alone issues no token — the university email must be verified.
    verified = client.post(
        "/api/auth/verify-email",
        json={"email": "intruder@student.edu", "code": intruder.json()["devVerificationCode"]},
    )
    assert verified.status_code == 200, verified.text
    intruder_headers = {"Authorization": f"Bearer {verified.json()['accessToken']}"}

    for path in ("", "/status", "/results", "/transcript", "/notes"):
        response = client.get(f"/api/lectures/{lecture_id}{path}", headers=intruder_headers)
        assert response.status_code == 404, f"{path} leaked another student's lecture"

    assert client.get(f"/api/classes/{course['id']}", headers=intruder_headers).status_code == 404


def test_unsupported_upload_is_rejected(client: TestClient, new_user: dict) -> None:
    headers = new_user["headers"]
    course = _create_class(client, headers, title="Bad Upload")

    response = client.post(
        "/api/lectures",
        data={"courseId": course["id"]},
        files={"file": ("notes.pdf", b"%PDF-1.4 not audio", "application/pdf")},
        headers=headers,
    )
    assert response.status_code == 415, response.text

    empty = client.post(
        "/api/lectures",
        data={"courseId": course["id"]},
        files={"file": ("empty.txt", b"", "text/plain")},
        headers=headers,
    )
    assert empty.status_code in (415, 422), empty.text

    unknown_course = client.post(
        "/api/lectures",
        data={"courseId": "cls-does-not-exist"},
        files={"file": ("a.txt", b"hello world", "text/plain")},
        headers=headers,
    )
    assert unknown_course.status_code == 404, unknown_course.text
