"""Meeting access, guest joining, and audio recording endpoints."""

from __future__ import annotations

from pathlib import Path

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    HTTPException,
    Query,
    status,
)
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import settings
from app.db.session import get_db
from app.meeting.policy import assess_link, detect_platform, supported_platforms
from app.ml.stt import UnsupportedAudioError, validate_upload
from app.models import User
from app.schemas import (
    BotJoinOut,
    BotStatusOut,
    LectureCreatedOut,
    MeetingPolicyOut,
    MessageResponse,
)
from app.services import course_service, lecture_service
from app.services.audio_capture_service import (
    audio_capture_service,
    RecordingError,
)
from app.services.meeting_bot_service import meeting_bot

router = APIRouter(prefix="/meetings", tags=["meetings"])


@router.post("/join", response_model=BotJoinOut)
async def join_meeting(
    link: str,
    user: User = Depends(get_current_user),
) -> BotJoinOut:
    """Start the assistant bot, which requests admission from the host.

    The bot is launched in a real Chrome window and clicks "Ask to join"; the
    host still has to admit it. Poll `GET /meetings/bot/status` for the outcome.
    """
    platform = detect_platform(link)

    if not platform.automated_join_supported:
        return BotJoinOut(
            bot_id=None,
            status="unsupported",
            detail=(
                f"Automated joining is not supported for {platform.name}. "
                "Join the meeting yourself with your institute account, then "
                "upload the authorized recording or use live capture."
            ),
        )

    bot_id = await meeting_bot.join_meeting(link, f"Assistant ({user.name})")
    return BotJoinOut(
        bot_id=bot_id,
        status="starting",
        detail="Opening the assistant browser. Please watch for the Chrome window.",
    )


@router.get("/bot/status", response_model=BotStatusOut)
def bot_status(
    link: str = Query(..., description="The meeting link the bot is joining."),
    _user: User = Depends(get_current_user),
) -> BotStatusOut:
    """Live state of the assistant bot for a meeting link."""
    status = meeting_bot.status_for_link(link)
    if status is None:
        return BotStatusOut(found=False)
    return BotStatusOut(
        found=True,
        bot_id=status.get("botId"),
        link=status.get("link"),
        status=status.get("status"),
        detail=status.get("detail"),
        started_at=status.get("startedAt"),
        updated_at=status.get("updatedAt"),
    )


@router.post("/bot/stop", response_model=MessageResponse)
async def stop_bot(
    link: str,
    _user: User = Depends(get_current_user),
) -> MessageResponse:
    """Make the assistant bot leave the meeting and close its browser window."""
    stopped = await meeting_bot.stop_bot(meeting_bot.bot_id_for_link(link))
    return MessageResponse(
        message="Assistant left the meeting." if stopped else "No active assistant for this meeting."
    )


@router.get("/policy", response_model=MeetingPolicyOut)
def meeting_policy(
    link: str | None = Query(
        default=None,
        max_length=500,
        description="The meeting link the student pasted, if any.",
    ),
    _user: User = Depends(get_current_user),
) -> dict:
    """Explain meeting platform access and authorization policy."""
    assessed = assess_link(link)
    assessed["platforms"] = supported_platforms()
    return assessed


@router.post("/recording/start", response_model=MessageResponse)
def start_meeting_recording(
    course_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MessageResponse:
    """Start system-audio recording for an owned course."""

    try:
        course_service.get_course(db, user.id, course_id)

        result = audio_capture_service.start_recording(
            user_id=user.id,
            course_id=course_id,
        )

        return MessageResponse(message=result["message"])

    except course_service.NotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    except RecordingError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc


@router.post(
    "/recording/stop",
    response_model=LectureCreatedOut,
)
def stop_meeting_recording(
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Finalize the WAV and submit it to the existing lecture pipeline."""

    try:
        recording = audio_capture_service.stop_recording(user_id=user.id)

    except RecordingError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    file_path = Path(recording["file_path"])
    file_size = recording["file_size_bytes"]
    course_id = recording["course_id"]

    try:
        course = course_service.get_course(db, user.id, course_id)

        validate_upload(file_path, file_size)

        lecture, job = lecture_service.create_lecture(
            db=db,
            user=user,
            course=course,
            path=file_path,
            size=file_size,
            content_type="audio/wav",
            original_filename=file_path.name,
        )

        background_tasks.add_task(
            lecture_service.run_processing_job,
            lecture.id,
        )

        return lecture_service.to_lecture_created(db, lecture, job)

    except course_service.NotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    except UnsupportedAudioError as exc:
        error_status = (
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE
            if file_size > settings.max_upload_bytes
            else status.HTTP_415_UNSUPPORTED_MEDIA_TYPE
        )
        raise HTTPException(
            status_code=error_status,
            detail=str(exc),
        ) from exc
