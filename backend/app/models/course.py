"""Course (= one online class session the student joins) and its lectures.

A course is what the student sees in "My Classes". Each course can have one or
more lectures (recordings/transcripts uploaded or captured for that session);
each lecture is processed and produces transcript segments, a note and
extracted items.

This 1—* split keeps the existing frontend model intact: the UI navigates by
`classId`, and the API resolves "the class' results" to its latest lecture.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.user import utcnow

# Mirrors the frontend union in src/types/index.ts (ClassStatus)
COURSE_STATUSES = ("upcoming", "live", "completed", "processing")


class Course(Base):
    __tablename__ = "courses"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)

    title: Mapped[str] = mapped_column(String(200), nullable=False)
    subject: Mapped[str] = mapped_column(String(120), nullable=False)
    meeting_link: Mapped[str | None] = mapped_column(String(500), nullable=True)
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    duration_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="upcoming")

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    user: Mapped["User"] = relationship(back_populates="courses")  # noqa: F821
    lectures: Mapped[list["Lecture"]] = relationship(
        back_populates="course", cascade="all, delete-orphan", order_by="Lecture.created_at"
    )


# Mirrors the frontend ProcessingStageKey values
LECTURE_STATUSES = ("pending", "processing", "completed", "failed")

# How the audio/text reached the backend. Recorded honestly so the UI (and the
# report) can distinguish an uploaded recording from a live capture.
SOURCE_TYPES = ("upload_audio", "upload_transcript")


class Lecture(Base):
    __tablename__ = "lectures"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    course_id: Mapped[str] = mapped_column(
        ForeignKey("courses.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)

    source_type: Mapped[str] = mapped_column(String(24), default="upload_audio")
    original_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    stored_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    content_type: Mapped[str | None] = mapped_column(String(120), nullable=True)
    size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    duration_seconds: Mapped[float | None] = mapped_column(nullable=True)

    status: Mapped[str] = mapped_column(String(20), default="pending")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Which implementation actually produced each output. Recorded so results
    # are never mistaken for something a model did not do.
    stt_method: Mapped[str | None] = mapped_column(String(60), nullable=True)
    classifier_method: Mapped[str | None] = mapped_column(String(60), nullable=True)
    summarizer_method: Mapped[str | None] = mapped_column(String(60), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    course: Mapped["Course"] = relationship(back_populates="lectures")
    segments: Mapped[list["TranscriptSegment"]] = relationship(
        back_populates="lecture", cascade="all, delete-orphan", order_by="TranscriptSegment.index"
    )
    note: Mapped["Note | None"] = relationship(  # noqa: F821
        back_populates="lecture", cascade="all, delete-orphan", uselist=False
    )
    announcements: Mapped[list["Announcement"]] = relationship(  # noqa: F821
        back_populates="lecture", cascade="all, delete-orphan"
    )
    questions: Mapped[list["Question"]] = relationship(  # noqa: F821
        back_populates="lecture", cascade="all, delete-orphan"
    )
    action_items: Mapped[list["ActionItem"]] = relationship(  # noqa: F821
        back_populates="lecture", cascade="all, delete-orphan"
    )
    jobs: Mapped[list["ProcessingJob"]] = relationship(  # noqa: F821
        back_populates="lecture", cascade="all, delete-orphan"
    )
