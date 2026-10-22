"""Unit tests for the transcript / classification / extraction / summary stages.

These run on the deterministic baseline implementations, so they are fast and
need no model download. They verify correctness of behaviour, not model quality
(model quality is measured by backend/scripts/evaluate_classifier.py).
"""

from __future__ import annotations

from datetime import datetime, timezone

from app.ml import extractors
from app.ml.classifier import RuleBasedClassifier
from app.ml.dates import find_date
from app.ml.notes import ExtractiveSummarizer
from app.ml.transcript_io import parse_plain_text, parse_vtt_or_srt
from app.ml.types import PipelineSegment

REFERENCE = datetime(2026, 9, 16, tzinfo=timezone.utc)


def test_vtt_parsing_preserves_timestamps_and_speakers() -> None:
    vtt = (
        "WEBVTT\n\n"
        "00:00:01.000 --> 00:00:05.000\n"
        "<v Instructor>Convolution is a sliding dot product.\n\n"
        "00:00:05.500 --> 00:00:09.000\n"
        "<v Student>How do we pick the kernel size?\n"
    )
    parsed = parse_vtt_or_srt(vtt)
    assert parsed.had_timestamps is True
    assert len(parsed.segments) == 2
    assert parsed.segments[0].start == 1.0
    assert parsed.segments[0].end == 5.0
    assert parsed.segments[0].speaker == "Instructor"
    assert parsed.segments[1].speaker == "Student"


def test_srt_comma_milliseconds_are_supported() -> None:
    srt = "1\n00:00:02,500 --> 00:00:04,000\nPadding keeps the output size.\n"
    parsed = parse_vtt_or_srt(srt)
    assert len(parsed.segments) == 1
    assert parsed.segments[0].start == 2.5
    assert parsed.segments[0].end == 4.0


def test_plain_text_parsing_has_no_timestamps() -> None:
    parsed = parse_plain_text("Instructor: Pooling reduces the spatial size.\nStride moves the filter.")
    assert parsed.had_timestamps is False
    assert all(segment.start is None for segment in parsed.segments)
    assert parsed.segments[0].speaker == "Instructor"


def test_timeout_style_text_is_split_into_sentences() -> None:
    parsed = parse_plain_text("First point. Second point! Third point?")
    assert [segment.text for segment in parsed.segments] == [
        "First point.",
        "Second point!",
        "Third point?",
    ]


def test_baseline_classifier_separates_obvious_labels() -> None:
    classifier = RuleBasedClassifier()
    samples = [
        "How do we choose the size of the kernel?",
        "A convolution is defined as a sliding dot product between a filter and a patch.",
        "Let us discuss the trade-off between the two options.",
        "We have decided that we will use strided convolutions in the final project.",
        "Please submit the notebook before the deadline.",
    ]
    expected = ["QUESTION", "INFORMATION", "DISCUSSION", "DECISION", "ACTION_ITEM"]
    predictions = classifier.classify(samples)
    assert [p.label for p in predictions] == expected
    assert all(0.0 < p.confidence <= 1.0 for p in predictions)
    assert all(p.method == RuleBasedClassifier.method for p in predictions)


def test_classifier_confidence_is_low_for_ambiguous_short_text() -> None:
    """The baseline must not report high certainty on content-free input."""
    prediction = RuleBasedClassifier().classify(["Okay."])[0]
    assert prediction.label == "INFORMATION"  # prior, not a claim
    assert prediction.confidence < 0.4


def test_questions_extraction_skips_meta_questions() -> None:
    segments = [
        PipelineSegment(index=0, text="Are there any questions before we finish?"),
        PipelineSegment(index=1, text="How does stride affect the output size?", speaker="Student"),
        PipelineSegment(index=2, text="Does that make sense to everyone?"),
    ]
    questions = extractors.extract_questions(segments)
    assert [q.text for q in questions] == ["How does stride affect the output size?"]


def test_announcement_categories_match_the_frontend_union() -> None:
    segments = [
        PipelineSegment(index=0, text="Please note that the assignment deadline is September 23."),
        PipelineSegment(index=1, text="There will be a short quiz at the start of next class."),
        PipelineSegment(index=2, text="The midterm exam will cover everything up to this lecture."),
        PipelineSegment(index=3, text="Next week's class has been moved from Thursday to Friday."),
        PipelineSegment(index=4, text="Assignment 3 is posted, please submit a working notebook."),
        PipelineSegment(index=5, text="Office hours this week are extended by thirty minutes."),
    ]
    announcements = extractors.extract_announcements(segments, REFERENCE)
    categories = {a.category for a in announcements}
    assert "Deadline" in categories
    assert "Quiz" in categories
    assert "Exam" in categories
    assert "Schedule Change" in categories
    assert "Assignment" in categories
    assert "General Announcement" in categories


def test_deadline_is_only_resolved_when_the_transcript_states_it() -> None:
    resolved = find_date("the deadline is September 23", REFERENCE)
    assert resolved is not None and resolved.resolved is not None
    assert resolved.resolved.month == 9 and resolved.resolved.day == 23
    assert resolved.uncertain is False

    vague = find_date("submit it sometime next week", REFERENCE)
    assert vague is not None and vague.resolved is None and vague.uncertain is True


def test_action_items_capture_assignee_and_kind() -> None:
    segments = [
        PipelineSegment(index=0, text="All students should complete the lab exercise by Friday."),
        PipelineSegment(index=1, text="Please upload your notebook to the portal."),
    ]
    items = extractors.extract_action_items(segments, REFERENCE)
    assert len(items) == 2
    assert items[0].assignee == "Students"
    assert items[0].due_at is not None
    assert {item.kind for item in items} <= {"assignment", "action_item", "deadline"}


def test_extractive_summary_uses_only_transcript_sentences() -> None:
    segments = [
        PipelineSegment(index=i, text=text)
        for i, text in enumerate(
            [
                "A convolution is defined as a sliding dot product between a filter and a local patch.",
                "Stride controls how far the filter moves at each step in the convolution.",
                "Pooling reduces the spatial size of the feature map and keeps strong activations.",
                "Parameter sharing reduces the number of weights in the convolution compared to dense layers.",
                "Early convolution layers learn edges while deeper layers learn shapes and objects.",
            ]
        )
    ]
    note = ExtractiveSummarizer().generate(segments, questions=[])
    assert note.summary
    # Every sentence in the summary must exist verbatim in the transcript.
    for sentence in note.summary.split(". "):
        assert sentence.strip().rstrip(".") in " ".join(s.text for s in segments)
    assert note.topics
    assert any(section["heading"] == "Key Concepts" for section in note.sections)
    assert note.method == "extractive-textrank-lite-v1"


def test_summarizer_handles_empty_input() -> None:
    note = ExtractiveSummarizer().generate([], questions=[])
    assert note.summary == ""
    assert note.sections == []
