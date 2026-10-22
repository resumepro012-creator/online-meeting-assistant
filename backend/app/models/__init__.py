"""Import every model so `Base.metadata` is complete (used by init_db/tests)."""

from app.models.course import COURSE_STATUSES, LECTURE_STATUSES, SOURCE_TYPES, Course, Lecture
from app.models.outputs import (
    ACTION_ITEM_KINDS,
    ANNOUNCEMENT_CATEGORIES,
    SEGMENT_CATEGORIES,
    ActionItem,
    Announcement,
    Note,
    ProcessingJob,
    Question,
    TranscriptSegment,
)
from app.models.user import User, utcnow

__all__ = [
    "ACTION_ITEM_KINDS",
    "ANNOUNCEMENT_CATEGORIES",
    "COURSE_STATUSES",
    "LECTURE_STATUSES",
    "SEGMENT_CATEGORIES",
    "SOURCE_TYPES",
    "ActionItem",
    "Announcement",
    "Course",
    "Lecture",
    "Note",
    "ProcessingJob",
    "Question",
    "TranscriptSegment",
    "User",
    "utcnow",
]
