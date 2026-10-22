"""Course ("class session") queries used by the API layer."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.ids import new_id
from app.models import Announcement, Course, Lecture, Note, User
from app.schemas import CourseCreateRequest, DashboardSummaryOut


class NotFoundError(LookupError):
    pass


def create_course(db: Session, user: User, payload: CourseCreateRequest) -> Course:
    course = Course(
        id=new_id("cls-"),
        user_id=user.id,
        title=payload.title.strip(),
        subject=payload.subject.strip(),
        meeting_link=(payload.meeting_link or "").strip() or None,
        scheduled_at=payload.scheduled_at or datetime.now(timezone.utc),
        duration_minutes=payload.duration_minutes,
        status="upcoming",
    )
    db.add(course)
    db.commit()
    db.refresh(course)
    return course


def _course_query(user_id: str):
    return (
        select(Course)
        .where(Course.user_id == user_id)
        .options(selectinload(Course.lectures).selectinload(Lecture.note))
    )


def list_courses(db: Session, user_id: str) -> list[Course]:
    return list(db.scalars(_course_query(user_id).order_by(Course.scheduled_at.desc())).all())


def get_course(db: Session, user_id: str, course_id: str) -> Course:
    course = db.scalars(_course_query(user_id).where(Course.id == course_id)).first()
    if course is None:
        raise NotFoundError(f"Class '{course_id}' was not found.")
    return course


def latest_lecture(course: Course) -> Lecture | None:
    """Most recent lecture of a course — what `/classes/{id}/results` resolves to."""
    if not course.lectures:
        return None
    return max(course.lectures, key=lambda lecture: lecture.created_at)


def latest_completed_lecture(course: Course) -> Lecture | None:
    completed = [lecture for lecture in course.lectures if lecture.status == "completed"]
    if not completed:
        return None
    return max(completed, key=lambda lecture: lecture.completed_at or lecture.created_at)


def dashboard_summary(db: Session, user_id: str) -> DashboardSummaryOut:
    course_ids = select(Course.id).where(Course.user_id == user_id).scalar_subquery()
    total_classes = db.scalar(select(func.count()).select_from(Course).where(Course.user_id == user_id)) or 0
    classes_attended = (
        db.scalar(
            select(func.count())
            .select_from(Course)
            .where(Course.user_id == user_id, Course.status == "completed")
        )
        or 0
    )
    notes_generated = (
        db.scalar(select(func.count()).select_from(Note).where(Note.course_id.in_(course_ids))) or 0
    )
    important_announcements = (
        db.scalar(
            select(func.count()).select_from(Announcement).where(Announcement.course_id.in_(course_ids))
        )
        or 0
    )
    return DashboardSummaryOut(
        total_classes=total_classes,
        classes_attended=classes_attended,
        notes_generated=notes_generated,
        important_announcements=important_announcements,
    )
