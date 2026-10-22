"""Explicit ORM -> API schema serializers.

Deliberately written by hand rather than relying on automatic attribute mapping:
the API contract is the thing the frontend depends on, so it should be readable
and unambiguous in one place.
"""

from __future__ import annotations

from app.ml.stages import STAGES
from app.models import ActionItem, Announcement, Course, Lecture, Note, ProcessingJob, Question, TranscriptSegment, User
from app.schemas import (
    ActionItemOut,
    AnnouncementOut,
    CourseOut,
    JobStatusOut,
    LectureOut,
    NoteOut,
    NoteSectionOut,
    ProcessingStageOut,
    QuestionOut,
    StudentOut,
    TranscriptSegmentOut,
)


def to_student(user: User) -> StudentOut:
    return StudentOut(
        id=user.id,
        name=user.name,
        email=user.email,
        avatar_initials=user.avatar_initials,
        program=user.program,
    )


def course_has_notes(course: Course) -> bool:
    return any(lecture.note is not None for lecture in course.lectures)


def to_course(course: Course) -> CourseOut:
    return CourseOut(
        id=course.id,
        title=course.title,
        subject=course.subject,
        date=course.scheduled_at,
        duration_minutes=course.duration_minutes,
        status=course.status,
        meeting_link=course.meeting_link,
        has_notes=course_has_notes(course),
    )


def to_lecture(lecture: Lecture) -> LectureOut:
    return LectureOut(
        id=lecture.id,
        course_id=lecture.course_id,
        source_type=lecture.source_type,
        original_filename=lecture.original_filename,
        status=lecture.status,
        duration_seconds=lecture.duration_seconds,
        error_message=lecture.error_message,
        created_at=lecture.created_at,
        completed_at=lecture.completed_at,
    )


def to_job_status(job: ProcessingJob, lecture: Lecture) -> JobStatusOut:
    return JobStatusOut(
        job_id=job.id,
        lecture_id=lecture.id,
        course_id=lecture.course_id,
        status=job.status,
        stage=job.stage,
        progress=job.progress,
        message=job.message,
        error=job.error,
        stages=[ProcessingStageOut(key=key, label=label) for key, label in STAGES],
    )


def to_segment(segment: TranscriptSegment) -> TranscriptSegmentOut:
    return TranscriptSegmentOut(
        id=segment.id,
        index=segment.index,
        speaker=segment.speaker,
        text=segment.text,
        start_seconds=segment.start_seconds,
        end_seconds=segment.end_seconds,
        category=segment.category,
        confidence=segment.confidence,
        method=segment.method,
    )


def to_note(note: Note, course: Course) -> NoteOut:
    return NoteOut(
        id=note.id,
        class_id=course.id,
        title=note.title or course.title,
        subject=course.subject,
        date=note.created_at,
        preview=note.preview or "",
        summary=note.summary or "",
        topics=[str(t) for t in (note.topics or [])],
        sections=[
            NoteSectionOut(
                heading=str(section.get("heading", "")),
                points=[str(p) for p in section.get("points", [])],
            )
            for section in (note.sections or [])
        ],
        method=note.method,
    )


def to_announcement(announcement: Announcement, course: Course) -> AnnouncementOut:
    return AnnouncementOut(
        id=announcement.id,
        text=announcement.text,
        category=announcement.category,
        related_lecture=course.title,
        related_class_id=course.id,
        date=announcement.created_at,
        deadline=announcement.deadline,
        deadline_text=announcement.deadline_text,
        source_seconds=announcement.source_seconds,
    )


def to_question(question: Question) -> QuestionOut:
    return QuestionOut(
        id=question.id,
        text=question.text,
        speaker=question.speaker,
        source_seconds=question.source_seconds,
        is_ai_generated=question.is_ai_generated,
    )


def to_action_item(item: ActionItem) -> ActionItemOut:
    return ActionItemOut(
        id=item.id,
        kind=item.kind,
        text=item.text,
        assignee=item.assignee,
        due_at=item.due_at,
        due_text=item.due_text,
        due_uncertain=item.due_uncertain,
        source_seconds=item.source_seconds,
    )
