"""Class sessions, their generated outputs, and the dashboard summary."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models import Course, User
from app.schemas import (
    AnnouncementOut,
    CourseCreateRequest,
    CourseOut,
    DashboardSummaryOut,
    LectureOut,
    NoteOut,
    QuestionOut,
    ResultsOut,
)
from app.services import course_service, lecture_service
from app.services.serializers import to_announcement, to_course, to_lecture, to_note, to_question

router = APIRouter(prefix="/classes", tags=["classes"])


def _get_course_or_404(db: Session, user: User, course_id: str) -> Course:
    try:
        return course_service.get_course(db, user.id, course_id)
    except course_service.NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


def _require_lecture(db: Session, course: Course, course_id: str):
    lecture = course_service.latest_lecture(course)
    if lecture is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                f"Class '{course_id}' has no lecture yet. Upload a recording "
                "(POST /api/lectures) and start processing first."
            ),
        )
    return lecture


@router.post("", response_model=CourseOut, status_code=status.HTTP_201_CREATED)
def create_class(
    payload: CourseCreateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> CourseOut:
    course = course_service.create_course(db, user, payload)
    return to_course(course)


@router.get("", response_model=list[CourseOut])
def list_classes(
    db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> list[CourseOut]:
    return [to_course(course) for course in course_service.list_courses(db, user.id)]


@router.get("/{course_id}", response_model=CourseOut)
def get_class(
    course_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> CourseOut:
    return to_course(_get_course_or_404(db, user, course_id))


@router.get("/{course_id}/lectures", response_model=list[LectureOut])
def list_class_lectures(
    course_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> list[LectureOut]:
    course = _get_course_or_404(db, user, course_id)
    return [to_lecture(lecture) for lecture in sorted(course.lectures, key=lambda l: l.created_at)]


@router.get("/{course_id}/results", response_model=ResultsOut)
def class_results(
    course_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> ResultsOut:
    course = _get_course_or_404(db, user, course_id)
    lecture = _require_lecture(db, course, course_id)
    return lecture_service.build_results(db, course, lecture)


@router.get("/{course_id}/notes", response_model=NoteOut)
def class_notes(
    course_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> NoteOut:
    course = _get_course_or_404(db, user, course_id)
    lecture = course_service.latest_completed_lecture(course)
    if lecture is None or lecture.note is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No generated notes exist for class '{course_id}' yet.",
        )
    return to_note(lecture.note, course)


@router.get("/{course_id}/announcements", response_model=list[AnnouncementOut])
def class_announcements(
    course_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> list[AnnouncementOut]:
    course = _get_course_or_404(db, user, course_id)
    lecture = _require_lecture(db, course, course_id)
    results = lecture_service.build_results(db, course, lecture)
    return results.announcements


@router.get("/{course_id}/questions", response_model=list[QuestionOut])
def class_questions(
    course_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> list[QuestionOut]:
    course = _get_course_or_404(db, user, course_id)
    lecture = _require_lecture(db, course, course_id)
    return lecture_service.build_results(db, course, lecture).questions


# --------------------------------------------------------------------------- #
# Announcement inbox across every class + dashboard summary
# --------------------------------------------------------------------------- #
inbox_router = APIRouter(tags=["announcements"])


@inbox_router.get("/announcements", response_model=list[AnnouncementOut])
def all_announcements(
    class_id: str | None = Query(default=None, alias="classId"),
    category: str | None = Query(default=None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[AnnouncementOut]:
    from app.models import Announcement

    courses = {course.id: course for course in course_service.list_courses(db, user.id)}
    if not courses:
        return []

    query = (
        select(Announcement)
        .where(Announcement.course_id.in_(list(courses.keys())))
        .order_by(Announcement.created_at.desc(), Announcement.source_seconds.nulls_last())
    )
    if class_id:
        if class_id not in courses:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=f"Class '{class_id}' was not found."
            )
        query = query.where(Announcement.course_id == class_id)
    if category:
        query = query.where(Announcement.category == category)

    return [
        to_announcement(announcement, courses[announcement.course_id])
        for announcement in db.scalars(query).all()
    ]


dashboard_router = APIRouter(tags=["dashboard"])


@dashboard_router.get("/dashboard/summary", response_model=DashboardSummaryOut)
def summary(
    db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> DashboardSummaryOut:
    return course_service.dashboard_summary(db, user.id)


@dashboard_router.get("/dashboard/recent-classes", response_model=list[CourseOut])
def recent_classes(
    limit: int = Query(default=3, ge=1, le=50),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[CourseOut]:
    courses = [c for c in course_service.list_courses(db, user.id) if c.status == "completed"]
    return [to_course(course) for course in courses[:limit]]


# --------------------------------------------------------------------------- #
# Notes generated across every class ("Lecture Notes" page)
# --------------------------------------------------------------------------- #
notes_router = APIRouter(tags=["notes"])


@notes_router.get("/notes", response_model=list[NoteOut])
def all_notes(
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[NoteOut]:
    from app.models import Note

    courses = {course.id: course for course in course_service.list_courses(db, user.id)}
    if not courses:
        return []

    rows = db.scalars(
        select(Note)
        .where(Note.course_id.in_(list(courses.keys())))
        .order_by(Note.created_at.desc(), Note.id.desc())
        .limit(limit)
    ).all()
    return [to_note(row, courses[row.course_id]) for row in rows]
