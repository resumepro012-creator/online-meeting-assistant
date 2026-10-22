"""Meeting-access policy tests.

These assert the separation the brief demands: an authenticated university
account is **not** authorization to join an external meeting, and the system
says so instead of attempting to circumvent any access control.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.meeting.policy import NEVER_BYPASS_STATEMENT, detect_platform


def test_policy_endpoint_requires_a_verified_account(client: TestClient) -> None:
    assert client.get("/api/meetings/policy").status_code == 401


def test_google_meet_link_is_reported_as_not_auto_joinable(
    client: TestClient, new_user: dict
) -> None:
    response = client.get(
        "/api/meetings/policy",
        params={"link": "https://meet.google.com/abc-defg-hij"},
        headers=new_user["headers"],
    )
    assert response.status_code == 200, response.text
    body = response.json()

    assert body["platform"] == "google_meet"
    assert body["platformName"] == "Google Meet"
    assert body["linkRecognised"] is True
    # Application sign-in and meeting authorization are stated separately.
    assert body["applicationAuthenticationRequired"] is True
    assert body["meetingAuthorizationRequired"] is True
    assert body["automatedJoinSupported"] is False
    assert body["liveCaptureImplemented"] is False
    assert body["accessControls"], "the platform's access controls must be listed"
    assert body["permittedAlternative"]
    assert body["policy"] == NEVER_BYPASS_STATEMENT


def test_zoom_and_teams_links_are_detected(client: TestClient, new_user: dict) -> None:
    for link, expected in (
        ("https://us02web.zoom.us/j/1234567890", "zoom"),
        ("https://teams.microsoft.com/l/meetup-join/19%3ameeting", "microsoft_teams"),
        ("https://university.webex.com/meet/lecture", "webex"),
    ):
        body = client.get(
            "/api/meetings/policy", params={"link": link}, headers=new_user["headers"]
        ).json()
        assert body["platform"] == expected, link
        assert body["automatedJoinSupported"] is False


def test_unknown_platform_is_not_claimed_to_be_supported(
    client: TestClient, new_user: dict
) -> None:
    body = client.get(
        "/api/meetings/policy",
        params={"link": "https://meet.example.com/your-class"},
        headers=new_user["headers"],
    ).json()
    assert body["platform"] == "unknown"
    assert body["linkRecognised"] is False
    assert body["officialApiAvailable"] is False
    assert body["permittedAlternative"]


def test_no_link_still_explains_the_policy(client: TestClient, new_user: dict) -> None:
    body = client.get("/api/meetings/policy", headers=new_user["headers"]).json()
    assert body["providedLink"] is None
    assert body["automatedJoinSupported"] is False
    assert any("audio upload" in item for item in body["supportedInput"])


def test_platform_detection_accepts_schemeless_links() -> None:
    assert detect_platform("meet.google.com/abc-defg-hij").key == "google_meet"
    assert detect_platform("  ").key == "unknown"
    assert detect_platform(None).key == "unknown"


def test_no_platform_claims_automated_join_support() -> None:
    """Guards against a future change quietly re-enabling meeting automation."""
    for link in (
        "https://meet.google.com/x",
        "https://zoom.us/j/1",
        "https://teams.microsoft.com/l/meetup-join/1",
        "https://university.webex.com/meet/x",
    ):
        assert detect_platform(link).automated_join_supported is False
