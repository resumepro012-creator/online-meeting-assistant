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
from app.meeting.policy import assess_link, supported_platforms
from app.ml.stt import UnsupportedAudioError, validate_upload
from app.models import User
from app.schemas import MeetingPolicyOut, MessageResponse, LectureCreatedOut
from app.services import course_service, lecture_service
from app.services.audio_capture_service import (
    audio_capture_service,
    RecordingError,
)
from app.services.meeting_bot_service import meeting_bot

router = APIRouter(prefix="/meetings", tags=["meetings"])


@router.post("/join", response_model=MessageResponse)
async def join_meeting(
    link: str,
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user),
):
    """Start the guest bot. The host must admit it."""
    background_tasks.add_task(
        meeting_bot.join_meeting,
        link,
        f"Assistant ({user.name})",
    )
    return MessageResponse(
        message="Assistant Bot is joining the meeting. Please admit it from the waiting room."
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
