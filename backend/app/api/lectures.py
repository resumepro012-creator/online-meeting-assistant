"""Lecture upload, processing jobs, and result retrieval.

Milestone A of the brief ("reliable audio upload → real end-to-end processing")
is this router: upload a file, start processing, poll status, read results.
Live meeting capture (Phase 8 stages B-G) plugs into the same job pipeline later
without changing these endpoints.
"""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.ml.stt import UnsupportedAudioError
from app.models import TranscriptSegment, User
from app.schemas import (
    AnnouncementOut,
    JobStatusOut,
    LectureCreatedOut,
    LectureOut,
    NoteOut,
    QuestionOut,
    ResultsOut,
    TranscriptSegmentOut,
)
from app.services import course_service, lecture_service
from app.services.lecture_service import UploadTooLargeError
from app.services.serializers import to_job_status, to_lecture, to_note, to_segment

router = APIRouter(prefix="/lectures", tags=["lectures"])


def _user_lecture(db: Session, user: User, lecture_id: str):
    try:
        return lecture_service.get_lecture(db, user.id, lecture_id)
    except course_service.NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


def _course_of(db: Session, lecture):
    return course_service.get_course(db, lecture.user_id, lecture.course_id)


@router.post("", response_model=LectureCreatedOut, status_code=status.HTTP_201_CREATED)
async def upload_lecture(
    background_tasks: BackgroundTasks,
    course_id: str = Form(..., alias="courseId"),
    file: UploadFile = File(...),
    start_processing: bool = Form(default=True, alias="startProcessing"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> LectureCreatedOut:
    """Uploads a recording/transcript and (by default) starts processing."""
    try:
        course = course_service.get_course(db, user.id, course_id)
    except course_service.NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    try:
        path, size, content_type = await lecture_service.store_upload(file, course.id)
    except UploadTooLargeError as exc:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail=str(exc)) from exc
    except UnsupportedAudioError as exc:
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail=str(exc)) from exc

    lecture, job = lecture_service.create_lecture(
        db,
        user=user,
        course=course,
        path=path,
        size=size,
        content_type=content_type,
        original_filename=file.filename or path.name,
    )

    if start_processing:
        background_tasks.add_task(lecture_service.run_processing_job, lecture.id)

    return lecture_service.to_lecture_created(db, lecture, job)


@router.get("/{lecture_id}", response_model=LectureOut)
def get_lecture(
    lecture_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> LectureOut:
    return to_lecture(_user_lecture(db, user, lecture_id))


@router.post("/{lecture_id}/process", response_model=LectureCreatedOut)
def process_lecture(
    lecture_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> LectureCreatedOut:
    """(Re)runs the pipeline for an uploaded lecture, replacing earlier results."""
    lecture = _user_lecture(db, user, lecture_id)
    job = lecture_service.queue_processing(db, lecture)
    background_tasks.add_task(lecture_service.run_processing_job, lecture.id)
    return lecture_service.to_lecture_created(db, lecture, job)


@router.get("/{lecture_id}/status", response_model=JobStatusOut)
def get_status(
    lecture_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> JobStatusOut:
    lecture = _user_lecture(db, user, lecture_id)
    job = lecture_service.latest_job(db, lecture.id)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No processing job exists for this lecture yet. Call POST /api/lectures/{id}/process first.",
        )
    return to_job_status(job, lecture)


@router.get("/{lecture_id}/results", response_model=ResultsOut)
def get_results(
    lecture_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> ResultsOut:
    lecture = _user_lecture(db, user, lecture_id)
    course = _course_of(db, lecture)
    return lecture_service.build_results(db, course, lecture)


@router.get("/{lecture_id}/transcript", response_model=list[TranscriptSegmentOut])
def get_transcript(
    lecture_id: str,
    category: str | None = Query(default=None, description="Filter by predicted label"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[TranscriptSegmentOut]:
    lecture = _user_lecture(db, user, lecture_id)
    query = (
        select(TranscriptSegment)
        .where(TranscriptSegment.lecture_id == lecture.id)
        .order_by(TranscriptSegment.index)
    )
    if category:
        query = query.where(TranscriptSegment.category == category.upper())
    return [to_segment(segment) for segment in db.scalars(query).all()]


@router.get("/{lecture_id}/notes", response_model=NoteOut)
def get_notes(
    lecture_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> NoteOut:
    lecture = _user_lecture(db, user, lecture_id)
    course = _course_of(db, lecture)
    if lecture.note is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No notes exist for lecture '{lecture_id}' yet (status: {lecture.status}).",
        )
    return to_note(lecture.note, course)


@router.get("/{lecture_id}/announcements", response_model=list[AnnouncementOut])
def get_announcements(
    lecture_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> list[AnnouncementOut]:
    lecture = _user_lecture(db, user, lecture_id)
    course = _course_of(db, lecture)
    return lecture_service.build_results(db, course, lecture).announcements


@router.get("/{lecture_id}/questions", response_model=list[QuestionOut])
def get_questions(
    lecture_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> list[QuestionOut]:
    lecture = _user_lecture(db, user, lecture_id)
    course = _course_of(db, lecture)
    return lecture_service.build_results(db, course, lecture).questions
