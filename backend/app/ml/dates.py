"""Date/deadline phrase resolution for announcements and action items.

Policy: only resolve a date when the transcript states one that can be pinned
down. Relative or vague phrases ("next week", "after the break") are kept as
raw text with `uncertain=True` instead of being guessed into a calendar date.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta

MONTHS = {
    "january": 1, "jan": 1, "february": 2, "feb": 2, "march": 3, "mar": 3,
    "april": 4, "apr": 4, "may": 5, "june": 6, "jun": 6, "july": 7, "jul": 7,
    "august": 8, "aug": 8, "september": 9, "sept": 9, "sep": 9, "october": 10,
    "oct": 10, "november": 11, "nov": 11, "december": 12, "dec": 12,
}

WEEKDAYS = {
    "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
    "friday": 4, "saturday": 5, "sunday": 6,
}

_ISO = re.compile(r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b")
_DAY_MONTH = re.compile(
    r"\b(\d{1,2})(?:st|nd|rd|th)?\s+(?:of\s+)?(" + "|".join(MONTHS) + r")\b(?:,?\s*(\d{4}))?",
    re.IGNORECASE,
)
_MONTH_DAY = re.compile(
    r"\b(" + "|".join(MONTHS) + r")\s+(\d{1,2})(?:st|nd|rd|th)?\b(?:,?\s*(\d{4}))?",
    re.IGNORECASE,
)
_NUMERIC = re.compile(r"\b(\d{1,2})[/.](\d{1,2})(?:[/.](\d{2,4}))?\b")
_TIME = re.compile(r"\b(\d{1,2})(?::(\d{2}))?\s*(am|pm)\b", re.IGNORECASE)
_WEEKDAY = re.compile(
    r"\b(?:by\s+|on\s+|before\s+)?(next\s+|this\s+|coming\s+)?(" + "|".join(WEEKDAYS) + r")\b",
    re.IGNORECASE,
)

_VAGUE = re.compile(
    r"\b(next week|this week|next month|this month|next class|next session|"
    r"end of the week|end of the month|end of the day|after the break|"
    r"after class|before the break|soon|later|the weekend|this weekend|in a few days)\b",
    re.IGNORECASE,
)

_RELATIVE_DAYS = {
    "tomorrow": 1,
    "tonight": 0,
    "today": 0,
    "day after tomorrow": 2,
}


@dataclass
class DateMatch:
    resolved: datetime | None
    text: str
    uncertain: bool = False


def _apply_time(dt: datetime, text: str) -> datetime:
    match = _TIME.search(text)
    if not match:
        return dt.replace(hour=23, minute=59, second=0, microsecond=0)
    hour = int(match.group(1)) % 12
    minute = int(match.group(2) or 0)
    if match.group(3).lower() == "pm":
        hour += 12
    return dt.replace(hour=hour, minute=minute, second=0, microsecond=0)


def find_date(text: str, reference: datetime) -> DateMatch | None:
    """Finds the first resolvable date phrase in `text`.

    `reference` is normally the lecture date, used to anchor year-less and
    relative expressions.
    """
    lowered = text.lower()

    match = _ISO.search(text)
    if match:
        try:
            dt = datetime(int(match.group(1)), int(match.group(2)), int(match.group(3)))
            return DateMatch(_apply_time(dt, text), match.group(0))
        except ValueError:
            pass

    for regex, order in ((_DAY_MONTH, "dm"), (_MONTH_DAY, "md")):
        match = regex.search(text)
        if match:
            if order == "dm":
                day, month_name, year = match.group(1), match.group(2), match.group(3)
            else:
                month_name, day, year = match.group(1), match.group(2), match.group(3)
            try:
                dt = datetime(int(year) if year else reference.year, MONTHS[month_name.lower()], int(day))
            except ValueError:
                continue
            if not year and dt.date() < reference.date() - timedelta(days=1):
                dt = dt.replace(year=dt.year + 1)  # "Sept 23" said in December means next year
            return DateMatch(_apply_time(dt, text), match.group(0))

    match = _NUMERIC.search(text)
    if match:
        day, month, year = match.group(1), match.group(2), match.group(3)
        try:
            resolved_year = int(year) if year else reference.year
            if resolved_year < 100:
                resolved_year += 2000
            dt = datetime(resolved_year, int(month), int(day))
            return DateMatch(_apply_time(dt, text), match.group(0))
        except ValueError:
            pass

    for phrase, offset_days in _RELATIVE_DAYS.items():
        if re.search(rf"\b{re.escape(phrase)}\b", lowered):
            dt = reference + timedelta(days=offset_days)
            return DateMatch(_apply_time(dt, text), phrase)

    match = _WEEKDAY.search(text)
    if match:
        modifier = (match.group(1) or "").strip().lower()
        weekday = WEEKDAYS[match.group(2).lower()]
        days_ahead = (weekday - reference.weekday()) % 7
        if modifier in ("next", "coming"):
            days_ahead += 7 if days_ahead <= 1 else 0
        elif days_ahead == 0:
            days_ahead = 7
        dt = reference + timedelta(days=days_ahead)
        return DateMatch(_apply_time(dt, text), match.group(0))

    vague = _VAGUE.search(text)
    if vague:
        return DateMatch(None, vague.group(0), uncertain=True)

    return None
