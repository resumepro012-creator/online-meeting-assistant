"""Transcript segments + generated outputs (notes, announcements, Q&A, tasks)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.user import utcnow

# Target label set for the segment classifier (Phase 6 of the project brief).
SEGMENT_CATEGORIES = (
    "QUESTION",
    "INFORMATION",
    "DISCUSSION",
    "DECISION",
    "ACTION_ITEM",
)

# Announcement categories — must stay in sync with the frontend union
# AnnouncementCategory in src/types/index.ts.
ANNOUNCEMENT_CATEGORIES = (
    "Assignment",
    "Quiz",
    "Exam",
    "Deadline",
    "Schedule Change",
    "General Announcement",
)

# Action-item kinds (assignments / deadlines / generic to-dos).
ACTION_ITEM_KINDS = ("assignment", "deadline", "action_item")


class TranscriptSegment(Base):
    __tablename__ = "transcript_segments"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    lecture_id: Mapped[str] = mapped_column(
        ForeignKey("lectures.id", ondelete="CASCADE"), index=True
    )
    index: Mapped[int] = mapped_column(Integer, nullable=False)

    speaker: Mapped[str | None] = mapped_column(String(60), nullable=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    start_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    end_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Filled in by the classifier stage. `method` records HOW the label was
    # produced (real transformer model vs. documented baseline).
    category: Mapped[str | None] = mapped_column(String(20), nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    method: Mapped[str | None] = mapped_column(String(60), nullable=True)

    lecture: Mapped["Lecture"] = relationship(back_populates="segments")  # noqa: F821


class Note(Base):
    """Lecture summary + structured notes (one per lecture).

    `topics` and `sections` are stored as JSON because they map 1:1 onto the
    frontend `LectureNote.topics: string[]` and `LectureNote.sections:
    NoteSection[]` shapes, and are always written/read as a whole.
    """

    __tablename__ = "notes"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    lecture_id: Mapped[str] = mapped_column(
        ForeignKey("lectures.id", ondelete="CASCADE"), index=True, unique=True
    )
    course_id: Mapped[str] = mapped_column(ForeignKey("courses.id", ondelete="CASCADE"), index=True)

    title: Mapped[str] = mapped_column(String(200), nullable=False)
    preview: Mapped[str] = mapped_column(Text, default="")
    summary: Mapped[str] = mapped_column(Text, default="")
    # Grounded in the transcript by the extractive summarizer; `method` records
    # which summarizer produced it.
    method: Mapped[str | None] = mapped_column(String(60), nullable=True)
    is_ai_generated: Mapped[bool] = mapped_column(Boolean, default=True)
    topics: Mapped[list] = mapped_column(JSON, default=list)
    sections: Mapped[list] = mapped_column(JSON, default=list)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    lecture: Mapped["Lecture"] = relationship(back_populates="note")  # noqa: F821


class Announcement(Base):
    __tablename__ = "announcements"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    lecture_id: Mapped[str] = mapped_column(
        ForeignKey("lectures.id", ondelete="CASCADE"), index=True
    )
    course_id: Mapped[str] = mapped_column(ForeignKey("courses.id", ondelete="CASCADE"), index=True)

    text: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String(30), default="General Announcement")
    # Only set when the transcript actually stated a date. Never guessed.
    deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deadline_text: Mapped[str | None] = mapped_column(String(120), nullable=True)
    source_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    method: Mapped[str | None] = mapped_column(String(60), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    lecture: Mapped["Lecture"] = relationship(back_populates="announcements")  # noqa: F821


class Question(Base):
    """A question actually asked during the lecture (extracted, not invented)."""

    __tablename__ = "questions"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    lecture_id: Mapped[str] = mapped_column(
        ForeignKey("lectures.id", ondelete="CASCADE"), index=True
    )
    text: Mapped[str] = mapped_column(Text, nullable=False)
    speaker: Mapped[str | None] = mapped_column(String(60), nullable=True)
    source_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    # False = asked in the lecture. Reserved for a future "AI revision
    # question" feature so the two are never confused.
    is_ai_generated: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    lecture: Mapped["Lecture"] = relationship(back_populates="questions")  # noqa: F821


class ActionItem(Base):
    __tablename__ = "action_items"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    lecture_id: Mapped[str] = mapped_column(
        ForeignKey("lectures.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[str] = mapped_column(String(20), default="action_item")
    text: Mapped[str] = mapped_column(Text, nullable=False)
    assignee: Mapped[str | None] = mapped_column(String(120), nullable=True)
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    due_text: Mapped[str | None] = mapped_column(String(120), nullable=True)
    # True when a due phrase was found but could not be resolved to a date
    # ("next week", "after the break") — surfaced as uncertain, not guessed.
    due_uncertain: Mapped[bool] = mapped_column(Boolean, default=False)
    source_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    lecture: Mapped["Lecture"] = relationship(back_populates="action_items")  # noqa: F821


class ProcessingJob(Base):
    __tablename__ = "processing_jobs"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    lecture_id: Mapped[str] = mapped_column(
        ForeignKey("lectures.id", ondelete="CASCADE"), index=True
    )
    status: Mapped[str] = mapped_column(String(20), default="queued")
    stage: Mapped[str] = mapped_column(String(30), default="preparing")
    progress: Mapped[int] = mapped_column(Integer, default=0)
    message: Mapped[str | None] = mapped_column(String(255), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    lecture: Mapped["Lecture"] = relationship(back_populates="jobs")  # noqa: F821
