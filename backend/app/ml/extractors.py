"""Grounded extraction of questions, announcements, deadlines and action items.

The project brief allows announcements/deadlines to be extracted with rules as
long as the method is documented and evaluated — that is what this module is.
Everything it returns is a sentence that literally exists in the transcript; it
never rewrites, completes or invents content.

The same signals could later be replaced by a trained token-classification
model; `run_extraction` is the single seam where that swap would happen.
"""

from __future__ import annotations

import re
from datetime import datetime

from app.ml.dates import find_date
from app.ml.text_utils import is_question, normalize_whitespace
from app.ml.types import ExtractedItem, PipelineSegment

METHOD = "rules-v1"

# --- announcement triggers -------------------------------------------------- #
_ANNOUNCE_TRIGGER = re.compile(
    r"\b(announce|announcement|reminder|remind you|please note|please remember|"
    r"important|be aware|heads up|just so you know|make a note|"
    r"office hours|no class|class is cancelled|class is canceled)\b",
    re.IGNORECASE,
)
_SCHEDULE_CHANGE = re.compile(
    r"\b(moved|move to|postponed|rescheduled|reschedule|cancelled|canceled|"
    r"pushed (?:back|forward)|new time|time slot|instead of|swapped|shifted)\b",
    re.IGNORECASE,
)
_EXAM = re.compile(r"\b(midterm|final exam|final exam|exam|test)\b", re.IGNORECASE)
_QUIZ = re.compile(r"\b(quiz|quizzes|pop quiz)\b", re.IGNORECASE)
_ASSIGNMENT_WORD = re.compile(
    r"\b(assignment|homework|problem set|project|report|lab report|presentation|notebook)\b",
    re.IGNORECASE,
)
_ASSIGNMENT_ACTION = re.compile(
    r"\b(submit|submission|submitted|hand in|upload|uploaded|posted|post|deliver|due|deadline|"
    r"complete|completed)\b",
    re.IGNORECASE,
)
_DEADLINE_WORD = re.compile(
    r"\b(deadline|due by|due on|due date|due this|submit by|submission by|last date|"
    r"no later than|must be submitted)\b",
    re.IGNORECASE,
)

# --- action item triggers --------------------------------------------------- #
_ACTION_TRIGGER = re.compile(
    r"\b(please\s+\w+|make sure|be sure to|don't forget|do not forget|remember to|"
    r"you need to|you should|you must|you have to|we need to|everyone should|"
    r"all students should|each group|each team|submit|upload|complete the|"
    r"read (?:chapter|the chapter|section)|revise|prepare|start working on|work on)\b",
    re.IGNORECASE,
)

_ASSIGNEE = re.compile(
    r"\b(all students|students|everyone|everybody|each group|each team|each student|"
    r"per group|per team|group\s+\d+|team\s+\d+|you all|the class|your group|your team)\b",
    re.IGNORECASE,
)

# The instructor addressing the class directly ("you must submit…"). The audience
# of a lecture is the students, so this is still a literal reading of the text —
# it never names a person who was not addressed.
_SECOND_PERSON = re.compile(r"\byou(?:r|rs|'re|'ll|'ve)?\b", re.IGNORECASE)

# Meta questions that address the room rather than ask about the content.
_META_QUESTION = re.compile(
    r"^(any questions|any question|questions\?|are there (?:any )?questions?|"
    r"(?:if )?you (?:have|had) any questions?|do you (?:all )?have any questions?|"
    r"does that make sense|does it make sense|"
    r"are you (?:all )?with me|is everyone (?:following|clear|good)|"
    r"can everyone (?:see|hear)|do you (?:all )?(?:see|hear) me|"
    r"shall i (?:continue|move on)|should i go on|right\?)",
    re.IGNORECASE,
)

_SENTENCE_TRIM = re.compile(r"^[\s\-–—•*]+|[\s]+$")


def _clean(text: str) -> str:
    return _SENTENCE_TRIM.sub("", normalize_whitespace(text))


def _dedupe(items: list[ExtractedItem], key=lambda item: item.text.lower()) -> list[ExtractedItem]:
    seen: set[str] = set()
    result: list[ExtractedItem] = []
    for item in items:
        token = key(item)
        if token in seen:
            continue
        seen.add(token)
        result.append(item)
    return result


def _classify_announcement(text: str) -> str:
    """Maps a sentence onto the frontend's AnnouncementCategory union."""
    if _DEADLINE_WORD.search(text):
        return "Deadline"
    if _SCHEDULE_CHANGE.search(text):
        return "Schedule Change"
    if _EXAM.search(text):
        return "Exam"
    if _QUIZ.search(text):
        return "Quiz"
    if _ASSIGNMENT_WORD.search(text) and _ASSIGNMENT_ACTION.search(text):
        return "Assignment"
    return "General Announcement"


def _is_announcement(text: str) -> bool:
    if _ANNOUNCE_TRIGGER.search(text):
        return True
    if _SCHEDULE_CHANGE.search(text) and re.search(r"\b(class|lecture|session|exam|quiz|lab|test)\b", text, re.I):
        return True
    if _DEADLINE_WORD.search(text):
        return True
    if _ASSIGNMENT_WORD.search(text) and _ASSIGNMENT_ACTION.search(text):
        return True
    if _QUIZ.search(text) and re.search(
        r"\b(there will|will be|will take place|at the start|next class|next session|"
        r"scheduled|is on|tomorrow)\b",
        text,
        re.I,
    ):
        return True
    if _EXAM.search(text) and re.search(r"\b(will cover|will be|is on|scheduled|covers)\b", text, re.I):
        return True
    return False


def _extract_assignee(text: str) -> str | None:
    match = _ASSIGNEE.search(text)
    if match:
        raw = match.group(1).lower()
        if raw in ("students", "all students", "the class"):
            return "Students"
        if raw in ("everyone", "everybody"):
            return "Everyone"
        if raw in ("each group", "per group", "your group"):
            return "Each group"
        if raw in ("each team", "per team", "your team"):
            return "Each team"
        if raw.startswith("group"):
            return raw.title()
        if raw.startswith("team"):
            return raw.title()
        return raw.title()

    # No group was named, but the sentence addresses the class directly, e.g.
    # "you must submit a working notebook" — the task falls on the students.
    if _SECOND_PERSON.search(text):
        return "Students"
    return None


def _action_kind(text: str) -> str:
    if _ASSIGNMENT_WORD.search(text) and _ASSIGNMENT_ACTION.search(text):
        return "assignment"
    if _DEADLINE_WORD.search(text):
        return "deadline"
    return "action_item"


def extract_questions(segments: list[PipelineSegment]) -> list[ExtractedItem]:
    """Questions that appear in the transcript (asked by anyone present)."""
    items: list[ExtractedItem] = []
    for seg in segments:
        text = _clean(seg.text)
        if len(text) < 12:
            continue
        if _META_QUESTION.match(text):
            continue
        if seg.category == "QUESTION" or is_question(text):
            items.append(
                ExtractedItem(
                    text=text,
                    speaker=seg.speaker,
                    source_seconds=seg.start,
                )
            )
    return _dedupe(items)


def extract_announcements(
    segments: list[PipelineSegment], reference: datetime
) -> list[ExtractedItem]:
    """Explicit notices, schedule changes, assignments and stated deadlines."""
    items: list[ExtractedItem] = []
    for seg in segments:
        text = _clean(seg.text)
        if len(text) < 15 or not _is_announcement(text):
            continue
        category = _classify_announcement(text)
        date_match = find_date(text, reference)
        items.append(
            ExtractedItem(
                text=text,
                category=category,
                due_at=date_match.resolved if date_match else None,
                due_text=date_match.text if date_match else None,
                due_uncertain=bool(date_match and date_match.uncertain),  # type: ignore[arg-type]
                source_seconds=seg.start,
            )
        )
    return _dedupe(items)


def extract_action_items(
    segments: list[PipelineSegment], reference: datetime
) -> list[ExtractedItem]:
    """Tasks/assignments/deadlines stated in the lecture, with assignee if given."""
    items: list[ExtractedItem] = []
    for seg in segments:
        text = _clean(seg.text)
        if len(text) < 15 or not _ACTION_TRIGGER.search(text):
            continue
        # Pure questions ("can you explain X?") are not task assignments.
        if is_question(text) and not _ACTION_TRIGGER.search(text[:40]):
            continue
        date_match = find_date(text, reference)
        items.append(
            ExtractedItem(
                text=text,
                kind=_action_kind(text),
                assignee=_extract_assignee(text),
                due_at=date_match.resolved if date_match else None,
                due_text=date_match.text if date_match else None,
                due_uncertain=bool(date_match and date_match.uncertain),  # type: ignore[arg-type]
                source_seconds=seg.start,
            )
        )
    return _dedupe(items)


def run_extraction(
    segments: list[PipelineSegment], reference: datetime
) -> tuple[list[ExtractedItem], list[ExtractedItem], list[ExtractedItem]]:
    """Returns (questions, announcements, action_items)."""
    return (
        extract_questions(segments),
        extract_announcements(segments, reference),
        extract_action_items(segments, reference),
    )
