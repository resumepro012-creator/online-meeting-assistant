"""End-to-end lecture processing pipeline.

    audio/transcript file
        -> validation
        -> speech-to-text (or transcript parsing)
        -> transcript segments (persisted)
        -> segment classification (deep-learning component)
        -> grounded extraction (questions / announcements / action items / deadlines)
        -> summary + structured notes
        -> persisted results + job progress

Every stage writes its `method` to the database, so a result can always be
traced back to the implementation that produced it. Failures are recorded on the
lecture + job with a human-readable message rather than being swallowed.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.ids import new_id
from app.ml import extractors
from app.ml.classifier import get_classifier
from app.ml.notes import get_summarizer
from app.ml.stages import DONE_PROGRESS, STAGE_PROGRESS
from app.ml.stt import UnsupportedAudioError, obtain_transcript, validate_upload
from app.ml.types import PipelineSegment
from app.models import (
    ActionItem,
    Announcement,
    Course,
    Lecture,
    Note,
    ProcessingJob,
    Question,
    TranscriptSegment,
)
from app.models.user import utcnow

logger = logging.getLogger(__name__)


class PipelineError(RuntimeError):
    """A failure with a message safe to show the student."""


def _latest_job(db: Session, lecture_id: str) -> ProcessingJob | None:
    return db.scalars(
        select(ProcessingJob)
        .where(ProcessingJob.lecture_id == lecture_id)
        .order_by(ProcessingJob.created_at.desc())
    ).first()


def _clear_previous_outputs(db: Session, lecture_id: str) -> None:
    """Re-processing a lecture replaces its results instead of duplicating them."""
    db.execute(delete(TranscriptSegment).where(TranscriptSegment.lecture_id == lecture_id))
    db.execute(delete(Announcement).where(Announcement.lecture_id == lecture_id))
    db.execute(delete(Question).where(Question.lecture_id == lecture_id))
    db.execute(delete(ActionItem).where(ActionItem.lecture_id == lecture_id))
    db.execute(delete(Note).where(Note.lecture_id == lecture_id))
    db.commit()


def _dedupe_segments(segments: list[PipelineSegment]) -> list[PipelineSegment]:
    """Drops consecutive repeats (common with overlapping live audio chunks)."""
    result: list[PipelineSegment] = []
    previous = ""
    for segment in segments:
        text = re.sub(r"\s+", " ", segment.text).strip()
        if not text:
            continue
        normalized = re.sub(r"[^a-z0-9 ]", "", text.lower())
        if normalized and normalized == previous:
            continue
        previous = normalized
        segment.text = text
        segment.index = len(result)
        result.append(segment)
    return result


def run_pipeline(db: Session, lecture_id: str) -> None:
    """Runs the full pipeline for one lecture. Never raises: failures are stored."""
    lecture = db.get(Lecture, lecture_id)
    if lecture is None:
        logger.error("Pipeline asked to process unknown lecture %s", lecture_id)
        return

    course = db.get(Course, lecture.course_id)
    job = _latest_job(db, lecture_id)

    def set_stage(stage: str, message: str | None = None) -> None:
        if job is not None:
            job.stage = stage
            job.status = "running"
            job.progress = STAGE_PROGRESS.get(stage, job.progress)
            job.message = message
            db.commit()
        logger.info("[lecture %s] stage=%s %s", lecture_id, stage, message or "")

    def fail(message: str, stage: str) -> None:
        lecture.status = "failed"
        lecture.error_message = message
        if job is not None:
            job.status = "failed"
            job.stage = stage
            job.error = message
            db.commit()
        if course is not None:
            has_completed_notes = db.scalars(
                select(Note.id).join(Lecture, Note.lecture_id == Lecture.id).where(
                    Lecture.course_id == course.id, Lecture.status == "completed"
                )
            ).first()
            course.status = "completed" if has_completed_notes else "upcoming"
            db.commit()
        logger.warning("[lecture %s] failed at %s: %s", lecture_id, stage, message)

    try:
        # ---------------------------------------------------------------- 1/6
        set_stage("preparing", "Validating the uploaded file…")
        if not lecture.stored_path:
            fail("No uploaded file is attached to this lecture.", "preparing")
            return
        path = Path(lecture.stored_path)
        if not path.exists():
            fail(f"Uploaded file is missing on disk: {path.name}", "preparing")
            return

        size = lecture.size_bytes or path.stat().st_size
        try:
            kind = validate_upload(path, size)
        except UnsupportedAudioError as exc:
            fail(str(exc), "preparing")
            return

        lecture.status = "processing"
        lecture.error_message = None
        if course is not None:
            course.status = "processing"
        _clear_previous_outputs(db, lecture_id)
        db.commit()

        # ---------------------------------------------------------------- 2/6
        set_stage(
            "transcribing",
            "Transcribing the recording locally…" if kind == "audio" else "Reading the transcript…",
        )
        try:
            transcription = obtain_transcript(path, kind)
        except UnsupportedAudioError as exc:
            fail(str(exc), "transcribing")
            return
        except Exception as exc:  # noqa: BLE001 — includes SpeechToTextUnavailable
            fail(str(exc), "transcribing")
            return

        if not transcription.segments:
            fail(
                "No speech could be detected in this recording, so no transcript was produced. "
                "Check that the file contains audible speech (silent or music-only recordings cannot be transcribed).",
                "transcribing",
            )
            return

        lecture.stt_method = transcription.method
        if transcription.duration_seconds:
            lecture.duration_seconds = transcription.duration_seconds
        db.commit()

        # ---------------------------------------------------------------- 3/6
        set_stage("analyzing", "Splitting the transcript into segments…")
        segments = _dedupe_segments(
            [
                PipelineSegment(
                    index=i,
                    text=raw.text,
                    speaker=raw.speaker,
                    start=raw.start,
                    end=raw.end,
                )
                for i, raw in enumerate(transcription.segments)
            ]
        )
        if not segments:
            fail("The transcript contained no usable text after cleaning.", "analyzing")
            return

        # ---------------------------------------------------------------- 4/6
        set_stage("identifying", "Classifying transcript segments…")
        try:
            classifier = get_classifier()
            predictions = classifier.classify([s.text for s in segments])
        except Exception as exc:  # noqa: BLE001
            fail(f"Segment classification failed: {exc}", "identifying")
            return

        for segment, prediction in zip(segments, predictions, strict=False):
            segment.category = prediction.label
            segment.confidence = prediction.confidence
            segment.method = prediction.method
        lecture.classifier_method = classifier.method
        db.commit()

        # Persist the classified transcript.
        for segment in segments:
            db.add(
                TranscriptSegment(
                    id=new_id("seg-"),
                    lecture_id=lecture.id,
                    index=segment.index,
                    speaker=segment.speaker,
                    text=segment.text,
                    start_seconds=segment.start,
                    end_seconds=segment.end,
                    category=segment.category,
                    confidence=segment.confidence,
                    method=segment.method,
                )
            )
        db.commit()

        # ---------------------------------------------------------------- 5/6
        set_stage("extracting", "Extracting announcements, questions and tasks…")
        reference = lecture.created_at or utcnow()
        if reference.tzinfo is None:
            reference = reference.replace(tzinfo=timezone.utc)
        reference_dt = datetime(
            reference.year, reference.month, reference.day, tzinfo=timezone.utc
        )
        questions, announcements, action_items = extractors.run_extraction(segments, reference_dt)

        for item in questions:
            db.add(
                Question(
                    id=new_id("q-"),
                    lecture_id=lecture.id,
                    text=item.text,
                    speaker=item.speaker,
                    source_seconds=item.source_seconds,
                    is_ai_generated=False,
                )
            )
        for item in announcements:
            db.add(
                Announcement(
                    id=new_id("ann-"),
                    lecture_id=lecture.id,
                    course_id=lecture.course_id,
                    text=item.text,
                    category=item.category or "General Announcement",
                    deadline=item.due_at if not item.due_uncertain else None,  # type: ignore[arg-type]
                    deadline_text=item.due_text,
                    source_seconds=item.source_seconds,
                    method=extractors.METHOD,
                )
            )
        for item in action_items:
            db.add(
                ActionItem(
                    id=new_id("ai-"),
                    lecture_id=lecture.id,
                    kind=item.kind or "action_item",
                    text=item.text,
                    assignee=item.assignee,
                    due_at=item.due_at if not item.due_uncertain else None,  # type: ignore[arg-type]
                    due_text=item.due_text,
                    due_uncertain=item.due_uncertain,
                    source_seconds=item.source_seconds,
                )
            )
        db.commit()

        # ---------------------------------------------------------------- 6/6
        set_stage("generating", "Generating the summary and structured notes…")
        summarizer = get_summarizer()
        note = summarizer.generate(segments, [q.text for q in questions])
        lecture.summarizer_method = getattr(summarizer, "method", None)

        db.add(
            Note(
                id=new_id("note-"),
                lecture_id=lecture.id,
                course_id=lecture.course_id,
                title=course.title if course else "Lecture",
                preview=note.preview,
                summary=note.summary,
                method=getattr(summarizer, "method", None),
                is_ai_generated=True,
                topics=note.topics,
                sections=note.sections,
            )
        )

        lecture.status = "completed"
        lecture.completed_at = utcnow()
        if course is not None:
            course.status = "completed"
            if lecture.duration_seconds:
                course.duration_minutes = max(1, round(lecture.duration_seconds / 60))
        if job is not None:
            job.status = "completed"
            job.progress = DONE_PROGRESS
            job.message = "Processing complete."
            job.error = None
        db.commit()
        logger.info(
            "[lecture %s] complete — %d segments, %d questions, %d announcements, %d action items",
            lecture_id,
            len(segments),
            len(questions),
            len(announcements),
            len(action_items),
        )

    except Exception as exc:  # noqa: BLE001 — last-resort guard so jobs never hang
        logger.exception("Unexpected pipeline failure for lecture %s", lecture_id)
        db.rollback()
        fail(f"Unexpected processing error: {exc}", (job.stage if job else "preparing"))
