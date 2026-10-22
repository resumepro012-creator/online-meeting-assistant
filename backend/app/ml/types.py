"""Shared pipeline data structures."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class PipelineSegment:
    """A transcript segment plus its classification result."""

    index: int
    text: str
    speaker: str | None = None
    start: float | None = None
    end: float | None = None
    category: str | None = None
    confidence: float | None = None
    method: str | None = None


@dataclass
class ExtractedItem:
    """A grounded item found in the transcript (question / announcement / task)."""

    text: str
    category: str | None = None
    kind: str | None = None
    speaker: str | None = None
    assignee: str | None = None
    due_at: object | None = None
    due_text: str | None = None
    due_uncertain: bool = False
    source_seconds: float | None = None
