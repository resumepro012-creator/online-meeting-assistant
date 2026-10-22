"""Lecture uploads, processing jobs and result assembly."""

from __future__ import annotations

import logging
import re
from pathlib import Path

from fastapi import UploadFile
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.ids import new_id
from app.ml.pipeline import run_pipeline
from app.ml.stt import TRANSCRIPT_EXTENSIONS, UnsupportedAudioError, validate_upload
from app.models import Course, Lecture, ProcessingJob, User
from app.schemas import LectureCreatedOut, PipelineInfoOut, ResultsOut
from app.services import course_service, serializers

logger = logging.getLogger(__name__)

_SAFE_NAME = re.compile(r"[^A-Za-z0-9._-]+")
_CHUNK = 1024 * 1024


class UploadTooLargeError(ValueError):
    pass


def _safe_filename(name: str) -> str:
    base = Path(name).name
    cleaned = _SAFE_NAME.sub("_", base).strip("._") or "upload"
    return cleaned[:120]


async def store_upload(upload: UploadFile, course_id: str) -> tuple[Path, int, str]:
    """Streams the upload to disk. Returns (path, size_bytes, content_type)."""
    original = upload.filename or "upload"
    suffix = Path(original).suffix.lower()
    if suffix not in TRANSCRIPT_EXTENSIONS and suffix not in {
        ".mp3", ".wav", ".m4a", ".mp4", ".webm", ".ogg", ".flac", ".aac", ".wma", ".mkv",
    }:
        raise UnsupportedAudioError(
            f"Unsupported file type '{suffix or 'unknown'}'. Upload audio "
            f"(.mp3/.wav/.m4a/.webm/.ogg/.flac) or a transcript (.txt/.vtt/.srt)."
        )

    target_dir = Path(settings.upload_dir) / course_id
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / f"{new_id()[:12]}-{_safe_filename(original)}"

    size = 0
    try:
        with target.open("wb") as out:
            while chunk := await upload.read(_CHUNK):
                size += len(chunk)
                if size > settings.max_upload_bytes:
                    out.close()
                    target.unlink(missing_ok=True)
                    raise UploadTooLargeError(
                        f"File exceeds the {settings.max_upload_mb} MB upload limit."
                    )
                out.write(chunk)
    except UploadTooLargeError:
        raise
    except OSError as exc:
        target.unlink(missing_ok=True)
        raise UnsupportedAudioError(f"Could not save the uploaded file: {exc}") from exc

    if size == 0:
        target.unlink(missing_ok=True)
        raise UnsupportedAudioError("The uploaded file is empty.")

    # Re-validate on disk (extension + size) before it is attached to a lecture.
    validate_upload(target, size)
    return target, size, upload.content_type or "application/octet-stream"


def get_lecture(db: Session, user_id: str, lecture_id: str) -> Lecture:
    lecture = db.scalars(
        select(Lecture).where(Lecture.id == lecture_id, Lecture.user_id == user_id)
    ).first()
    if lecture is None:
        raise course_service.NotFoundError(f"Lecture '{lecture_id}' was not found.")
    return lecture


def latest_job(db: Session, lecture_id: str) -> ProcessingJob | None:
    return db.scalars(
        select(ProcessingJob)
        .where(ProcessingJob.lecture_id == lecture_id)
        .order_by(ProcessingJob.created_at.desc(), ProcessingJob.id.desc())
    ).first()


def create_lecture(
    db: Session,
    user: User,
    course: Course,
    path: Path,
    size: int,
    content_type: str,
    original_filename: str,
) -> tuple[Lecture, ProcessingJob]:
    """Registers an uploaded file as a lecture and queues a processing job."""
    suffix = path.suffix.lower()
    source_type = "upload_transcript" if suffix in TRANSCRIPT_EXTENSIONS else "upload_audio"

    lecture = Lecture(
        id=new_id("lec-"),
        course_id=course.id,
        user_id=user.id,
        source_type=source_type,
        original_filename=original_filename,
        stored_path=str(path),
        content_type=content_type,
        size_bytes=size,
        status="pending",
    )
    db.add(lecture)
    db.flush()

    job = ProcessingJob(
        id=new_id("job-"),
        lecture_id=lecture.id,
        status="queued",
        stage="preparing",
        progress=0,
        message="Queued for processing.",
    )
    db.add(job)

    course.status = "processing"
    db.commit()
    db.refresh(lecture)
    db.refresh(job)
    return lecture, job


def queue_processing(db: Session, lecture: Lecture) -> ProcessingJob:
    """Creates a fresh job for (re)processing an existing lecture."""
    previous = latest_job(db, lecture.id)
    if previous and previous.status == "running":
        return previous

    job = ProcessingJob(
        id=new_id("job-"),
        lecture_id=lecture.id,
        status="queued",
        stage="preparing",
        progress=0,
        message="Queued for processing.",
    )
    db.add(job)
    lecture.status = "pending"
    lecture.error_message = None
    db.commit()
    db.refresh(job)
    return job


def run_processing_job(lecture_id: str) -> None:
    """Background entry point. Opens its own session because the request session
    is already closed by the time background tasks execute."""
    from app.db.session import SessionLocal

    db = SessionLocal()
    try:
        run_pipeline(db, lecture_id)
    finally:
        db.close()


def to_lecture_created(db: Session, lecture: Lecture, job: ProcessingJob) -> LectureCreatedOut:
    return LectureCreatedOut(
        lecture=serializers.to_lecture(lecture),
        job=serializers.to_job_status(job, lecture),
    )


def build_results(db: Session, course: Course, lecture: Lecture) -> ResultsOut:
    """Assembles the full result payload for a lecture."""
    from app.models import ActionItem, Announcement, Note, Question, TranscriptSegment

    note_row = db.scalars(select(Note).where(Note.lecture_id == lecture.id)).first()
    announcements = list(
        db.scalars(
            select(Announcement)
            .where(Announcement.lecture_id == lecture.id)
            .order_by(Announcement.source_seconds.nulls_last(), Announcement.created_at)
        ).all()
    )
    questions = list(
        db.scalars(
            select(Question)
            .where(Question.lecture_id == lecture.id)
            .order_by(Question.source_seconds.nulls_last(), Question.created_at)
        ).all()
    )
    action_items = list(
        db.scalars(
            select(ActionItem)
            .where(ActionItem.lecture_id == lecture.id)
            .order_by(ActionItem.source_seconds.nulls_last(), ActionItem.created_at)
        ).all()
    )
    segment_count = (
        db.scalar(
            select(func.count())
            .select_from(TranscriptSegment)
            .where(TranscriptSegment.lecture_id == lecture.id)
        )
        or 0
    )

    return ResultsOut(
        session=serializers.to_course(course),
        lecture=serializers.to_lecture(lecture),
        note=serializers.to_note(note_row, course) if note_row else None,
        announcements=[serializers.to_announcement(a, course) for a in announcements],
        questions=[serializers.to_question(q) for q in questions],
        action_items=[serializers.to_action_item(i) for i in action_items],
        pipeline=PipelineInfoOut(
            stt_method=lecture.stt_method,
            classifier_method=lecture.classifier_method,
            summarizer_method=lecture.summarizer_method,
            segment_count=segment_count,
        ),
    )
