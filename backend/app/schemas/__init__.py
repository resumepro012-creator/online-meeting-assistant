"""Request/response schemas.

Response field names deliberately mirror the existing frontend TypeScript types
(`src/types/index.ts`) so the UI does not need to change when it is wired to the
real API — e.g. `avatarInitials`, `hasNotes`, `relatedClassId`.

Requests accept camelCase (what the frontend sends) as well as snake_case.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator
from pydantic.alias_generators import to_camel


class CamelModel(BaseModel):
    """Base model: camelCase on the wire, snake_case in Python."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, from_attributes=True)


# --------------------------------------------------------------------------- #
# Auth
# --------------------------------------------------------------------------- #
class RegisterRequest(CamelModel):
    name: str = Field(min_length=1, max_length=120)
    email: EmailStr
    password: str = Field(min_length=6, max_length=128)
    program: str | None = Field(default=None, max_length=120)

    @field_validator("name")
    @classmethod
    def _name_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Name cannot be empty.")
        return v.strip()


class LoginRequest(CamelModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class StudentOut(CamelModel):
    id: str
    name: str
    email: str
    avatar_initials: str
    program: str | None = None


class AuthResponse(CamelModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    student: StudentOut


class RegisterResponse(CamelModel):
    """Returned by POST /api/auth/register.

    Deliberately contains **no token**: the account exists but stays inactive
    until the emailed verification code is confirmed.
    """

    email: str
    verification_required: bool = True
    message: str
    # Populated only when the development `console` email backend is in use, so
    # the flow can be completed without a mail server. Never set with real SMTP.
    dev_verification_code: str | None = None


class VerifyEmailRequest(CamelModel):
    email: EmailStr
    code: str = Field(min_length=4, max_length=12)


class ResendVerificationRequest(CamelModel):
    email: EmailStr


class ForgotPasswordRequest(CamelModel):
    email: EmailStr


class ResetPasswordRequest(CamelModel):
    token: str = Field(min_length=1, max_length=256)
    password: str = Field(min_length=6, max_length=128)


class MessageResponse(CamelModel):
    message: str


class ResendVerificationResponse(CamelModel):
    """Like `MessageResponse`, but may carry the code in development mode.

    With the `console` email backend the code has to reach the developer somehow
    (there is no inbox), so it is echoed here exactly as `RegisterResponse` does.
    With real SMTP `dev_verification_code` is always None.
    """

    message: str
    dev_verification_code: str | None = None


class AuthPolicyOut(CamelModel):
    """Describes the institute-email policy so the UI can show the right hint
    without hardcoding a domain."""

    allowed_email_domains: list[str]
    university_email_domains: list[str]
    # When true the UI should also accept any `.edu` / `.edu.<cc>` / `.ac.<cc>`
    # address, mirroring the backend's `is_allowed_email`.
    accept_any_academic_domain: bool = False
    verification_required: bool = True
    verification_code_length: int = 6
    resend_cooldown_seconds: int = 60
    dev_code_exposed: bool = False


# --------------------------------------------------------------------------- #
# Meeting access policy
# --------------------------------------------------------------------------- #
class MeetingPlatformOut(CamelModel):
    """One row of the platform table the UI displays."""

    key: str
    name: str
    automated_join_supported: bool = False
    official_api_available: bool = False


class MeetingPolicyOut(CamelModel):
    """What is / is not possible for a given meeting link.

    `application_authentication_required` (signed in here) and
    `meeting_authorization_required` (granted by the platform + host) are two
    separate things, and `automated_join_supported` is False for every platform.
    """

    provided_link: str | None = None
    link_recognised: bool = False
    platform: str
    platform_name: str
    application_authentication_required: bool = True
    meeting_authorization_required: bool = True
    automated_join_supported: bool = False
    official_api_available: bool = False
    api_note: str = ""
    access_controls: list[str] = Field(default_factory=list)
    permitted_alternative: str = ""
    policy: str
    live_capture_implemented: bool = False
    supported_input: list[str] = Field(default_factory=list)
    platforms: list[MeetingPlatformOut] = Field(default_factory=list)


# --------------------------------------------------------------------------- #
# Meeting assistant bot
# --------------------------------------------------------------------------- #
class BotJoinOut(CamelModel):
    """Result of asking the assistant bot to join a meeting.

    `bot_id` is None when the platform does not support automated joining, in
    which case `status` is `unsupported` and `detail` explains the alternative.
    """

    bot_id: str | None = None
    status: str
    detail: str = ""


class BotStatusOut(CamelModel):
    """Live state of the assistant bot for a given meeting link."""

    found: bool = False
    bot_id: str | None = None
    link: str | None = None
    status: str | None = None
    detail: str | None = None
    started_at: datetime | None = None
    updated_at: datetime | None = None


# --------------------------------------------------------------------------- #
# Courses / classes
# --------------------------------------------------------------------------- #
class CourseCreateRequest(CamelModel):
    title: str = Field(min_length=1, max_length=200)
    subject: str = Field(min_length=1, max_length=120)
    meeting_link: str | None = Field(default=None, max_length=500)
    scheduled_at: datetime | None = None
    duration_minutes: int | None = Field(default=None, ge=0, le=24 * 60)


class CourseOut(CamelModel):
    """Matches the frontend `ClassSession` type."""

    id: str
    title: str
    subject: str
    date: datetime
    duration_minutes: int | None = None
    status: str
    meeting_link: str | None = None
    has_notes: bool = False


class DashboardSummaryOut(CamelModel):
    total_classes: int
    classes_attended: int
    notes_generated: int
    important_announcements: int


# --------------------------------------------------------------------------- #
# Lectures / processing
# --------------------------------------------------------------------------- #
class LectureOut(CamelModel):
    id: str
    course_id: str
    source_type: str
    original_filename: str | None = None
    status: str
    duration_seconds: float | None = None
    error_message: str | None = None
    created_at: datetime
    completed_at: datetime | None = None


class ProcessingStageOut(CamelModel):
    key: str
    label: str


class JobStatusOut(CamelModel):
    """Drives the existing Processing page stepper."""

    job_id: str
    lecture_id: str
    course_id: str
    status: str
    stage: str
    progress: int
    message: str | None = None
    error: str | None = None
    stages: list[ProcessingStageOut] = []


class LectureCreatedOut(CamelModel):
    """Returned by POST /api/lectures and POST /api/lectures/{id}/process."""

    lecture: LectureOut
    job: JobStatusOut


class TranscriptSegmentOut(CamelModel):
    id: str
    index: int
    speaker: str | None = None
    text: str
    start_seconds: float | None = None
    end_seconds: float | None = None
    category: str | None = None
    confidence: float | None = None
    method: str | None = None


class NoteSectionOut(CamelModel):
    heading: str
    points: list[str]


class NoteOut(CamelModel):
    """Matches the frontend `LectureNote` type (classId = course id)."""

    id: str
    class_id: str
    title: str
    subject: str
    date: datetime
    preview: str
    summary: str
    topics: list[str]
    sections: list[NoteSectionOut]
    method: str | None = None


class AnnouncementOut(CamelModel):
    """Matches the frontend `Announcement` type."""

    id: str
    text: str
    category: str
    related_lecture: str
    related_class_id: str
    date: datetime
    deadline: datetime | None = None
    deadline_text: str | None = None
    source_seconds: float | None = None


class QuestionOut(CamelModel):
    id: str
    text: str
    speaker: str | None = None
    source_seconds: float | None = None
    is_ai_generated: bool = False


class ActionItemOut(CamelModel):
    id: str
    kind: str
    text: str
    assignee: str | None = None
    due_at: datetime | None = None
    due_text: str | None = None
    due_uncertain: bool = False
    source_seconds: float | None = None


class PipelineInfoOut(CamelModel):
    """Which implementation produced each output stage. Nothing is hidden."""

    stt_method: str | None = None
    classifier_method: str | None = None
    summarizer_method: str | None = None
    segment_count: int = 0


class ResultsOut(CamelModel):
    session: CourseOut
    lecture: LectureOut
    note: NoteOut | None = None
    announcements: list[AnnouncementOut] = []
    questions: list[QuestionOut] = []
    action_items: list[ActionItemOut] = []
    pipeline: PipelineInfoOut
