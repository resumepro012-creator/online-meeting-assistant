"""Pipeline stage definitions.

The keys/labels intentionally match the frontend's existing `ProcessingStage`
list (`src/data/mockData.ts`) so the Processing page keeps the same UI while
now being driven by real job status instead of a timer.
"""

from __future__ import annotations

STAGES: list[tuple[str, str]] = [
    ("preparing", "Preparing lecture content"),
    ("transcribing", "Transcribing audio"),
    ("analyzing", "Analyzing lecture content"),
    ("identifying", "Identifying important concepts"),
    ("extracting", "Extracting announcements"),
    ("generating", "Generating lecture notes"),
]

STAGE_KEYS = [key for key, _ in STAGES]

# Cumulative progress (%) reported when a stage starts.
STAGE_PROGRESS = {
    "preparing": 5,
    "transcribing": 20,
    "analyzing": 45,
    "identifying": 60,
    "extracting": 75,
    "generating": 90,
}

DONE_PROGRESS = 100


def stage_index(key: str) -> int:
    try:
        return STAGE_KEYS.index(key)
    except ValueError:
        return 0
