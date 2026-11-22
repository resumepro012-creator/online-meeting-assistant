"""Meeting-access policy.

Two different things are deliberately kept apart:

1. **Authentication into this application** — a verified university email
   address plus the JWT issued by `POST /api/auth/verify-email`. That is what
   the `/api` routes enforce.
2. **Authorization to join an external university meeting** — that is granted by
   the meeting platform (Google Meet, Zoom, Teams, Webex …) and by the meeting
   host, not by this application.

On platforms where an official, host-controlled path exists (currently Google
Meet), the assistant bot may open the meeting in its own browser and *ask* to
join on the student's behalf — the host still has to admit it. It never
bypasses waiting rooms, domain restrictions, host approval, lobby checks,
passcodes or any other access control, and it never records a meeting without
consent. For every other platform it tells the student plainly what the
platform allows and points at the permitted alternative: join the meeting
yourself with your official university account, then hand the assistant an
authorized recording or transcript.

Nothing here performs network calls — it is a policy/detection module only.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from urllib.parse import urlparse


@dataclass(frozen=True)
class MeetingPlatform:
    key: str
    name: str
    #: Hostname fragments that identify the platform.
    hosts: tuple[str, ...]
    #: True only when this project actually joins meetings by itself.
    automated_join_supported: bool
    #: Whether the vendor publishes an official, authorization-based API/SDK.
    official_api_available: bool
    api_note: str
    #: Controls the platform/host may require before letting anyone in.
    access_controls: tuple[str, ...] = field(default_factory=tuple)
    permitted_alternative: str = ""


_ALTERNATIVE = (
    "Join the meeting yourself using your official university account, then upload the "
    "authorized recording (or a transcript) here. The assistant processes audio and "
    "transcripts — it does not need to be inside the meeting."
)

_PLATFORMS: tuple[MeetingPlatform, ...] = (
    MeetingPlatform(
        key="google_meet",
        name="Google Meet",
        hosts=("meet.google.com", "meet.googleusercontent.com"),
        automated_join_supported=True,
        official_api_available=True,
        api_note=(
            "Google publishes the Meet REST API and the Google Workspace APIs, but they only "
            "work for a signed-in Workspace account that has been authorized by the account "
            "holder, and recording requires host/organizer permission in the Workspace domain."
        ),
        access_controls=(
            "Sign-in with a Google account inside the host's organization",
            "Host must admit you from the waiting room (knocking)",
            "Domain restriction on who may join",
            "Host approval before recording; Meet recording is a host-only control",
        ),
        permitted_alternative=_ALTERNATIVE,
    ),
    MeetingPlatform(
        key="zoom",
        name="Zoom",
        hosts=("zoom.us", "zoom.com", "zoomgov.com"),
        automated_join_supported=False,
        official_api_available=True,
        api_note=(
            "Zoom offers the Meeting SDK and REST APIs. A bot or server may only join when the "
            "account owner has authorized it via OAuth, the meeting does not require host "
            "admission, and the host has allowed it — cloud recording likewise needs host consent."
        ),
        access_controls=(
            "Meeting passcode / waiting room",
            "Zoom account authentication required by the host",
            "Host approval to enter",
            "Host consent required for recording",
        ),
        permitted_alternative=_ALTERNATIVE,
    ),
    MeetingPlatform(
        key="microsoft_teams",
        name="Microsoft Teams",
        hosts=("teams.microsoft.com", "teams.live.com", "teams.microsoft.us"),
        automated_join_supported=False,
        official_api_available=True,
        api_note=(
            "Microsoft Graph exposes Teams meetings and recordings, but only with a signed-in "
            "tenant account and the permissions granted by your university's IT administrator."
        ),
        access_controls=(
            "Sign-in with a university (tenant) account",
            "Lobby / waiting-room admission by the organizer",
            "Tenant policy on who may join or record",
            "Organizer approval before recording",
        ),
        permitted_alternative=_ALTERNATIVE,
    ),
    MeetingPlatform(
        key="webex",
        name="Cisco Webex",
        hosts=("webex.com", "webex.co.in"),
        automated_join_supported=False,
        official_api_available=True,
        api_note=(
            "Webex has REST APIs, but they require an authorized Webex account and the "
            "permissions granted by the meeting host or site administrator."
        ),
        access_controls=(
            "Meeting password / lobby",
            "Signed-in Webex account when required by the host",
            "Host admission",
            "Host consent for recording",
        ),
        permitted_alternative=_ALTERNATIVE,
    ),
)

UNKNOWN_PLATFORM = MeetingPlatform(
    key="unknown",
    name="Unknown or unsupported platform",
    hosts=(),
    automated_join_supported=False,
    official_api_available=False,
    api_note=(
        "This platform is not recognised, so no authorized integration exists for it."
    ),
    access_controls=(
        "Whatever access controls the platform and the host apply",
    ),
    permitted_alternative=_ALTERNATIVE,
)

#: A summary statement reused verbatim by the API and the UI, so both say the
#: same thing and neither overstates the capability.
NEVER_BYPASS_STATEMENT = (
    "This assistant never bypasses waiting rooms, domain restrictions, host approval, "
    "passcodes or any other access control, and never records a meeting without consent."
)


def detect_platform(link: str | None) -> MeetingPlatform:
    """Maps a meeting URL to a known platform, or `UNKNOWN_PLATFORM`."""
    if not link:
        return UNKNOWN_PLATFORM
    candidate = link.strip()
    if not candidate:
        return UNKNOWN_PLATFORM
    # Accept links typed without a scheme (e.g. "meet.google.com/abc-defg-hij").
    if "//" not in candidate:
        candidate = f"https://{candidate}"
    host = (urlparse(candidate).hostname or "").lower()
    if not host:
        return UNKNOWN_PLATFORM
    for platform in _PLATFORMS:
        if any(host == known or host.endswith(f".{known}") for known in platform.hosts):
            return platform
    return UNKNOWN_PLATFORM


def assess_link(link: str | None) -> dict:
    """Describes what is and is not possible for the given meeting link."""
    platform = detect_platform(link)
    return {
        "provided_link": link or None,
        "link_recognised": bool(link) and platform is not UNKNOWN_PLATFORM,
        "platform": platform.key,
        "platform_name": platform.name,
        # Reaching this code path already means the caller's university account
        # is authenticated; joining the meeting is a separate authorization.
        "application_authentication_required": True,
        "meeting_authorization_required": True,
        "automated_join_supported": platform.automated_join_supported,
        "official_api_available": platform.official_api_available,
        "api_note": platform.api_note,
        "access_controls": list(platform.access_controls),
        "permitted_alternative": platform.permitted_alternative,
        "policy": NEVER_BYPASS_STATEMENT,
        "live_capture_implemented": True,
        "supported_input": [
            "audio upload (.mp3, .wav, .m4a …)",
            "transcript (.txt, .vtt, .srt)",
            "live browser capture (tab audio)",
        ],
    }


def supported_platforms() -> list[dict]:
    """The platform table, for documentation and the UI."""
    return [
        {
            "key": platform.key,
            "name": platform.name,
            "automated_join_supported": platform.automated_join_supported,
            "official_api_available": platform.official_api_available,
        }
        for platform in (*_PLATFORMS, UNKNOWN_PLATFORM)
    ]
