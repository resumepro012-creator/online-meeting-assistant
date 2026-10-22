"""Transcript input: parsing uploaded .txt/.vtt/.srt files into segments.

Timestamps are preserved when the source format provides them (.vtt/.srt) and
are `None` for plain text — reported as unknown rather than invented.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class RawSegment:
    text: str
    start: float | None = None
    end: float | None = None
    speaker: str | None = None


@dataclass
class ParsedTranscript:
    segments: list[RawSegment] = field(default_factory=list)
    had_timestamps: bool = False

    @property
    def full_text(self) -> str:
        return " ".join(s.text for s in self.segments).strip()


_TS = r"(\d{1,2}):(\d{2}):(\d{2})[.,](\d{1,3})"
_CUE_RE = re.compile(rf"{_TS}\s*-->\s*{_TS}")
_VOICE_TAG_RE = re.compile(r"^<v\s+([^>]+)>", re.IGNORECASE)
_SPEAKER_LINE_RE = re.compile(r"^([A-Z][A-Za-z .'\-]{1,40}):\s+(.*)$")


def _to_seconds(h: str, m: str, s: str, ms: str) -> float:
    return int(h) * 3600 + int(m) * 60 + int(s) + int(ms.ljust(3, "0")) / 1000


def _clean_cue_text(text: str) -> tuple[str, str | None]:
    speaker = None
    match = _VOICE_TAG_RE.match(text.strip())
    if match:
        speaker = match.group(1).strip()
        text = text[match.end() :]
    text = re.sub(r"<[^>]+>", "", text)  # strip remaining cue tags
    return text.strip(), speaker


def parse_vtt_or_srt(content: str) -> ParsedTranscript:
    """Parses WebVTT or SubRip — both use the `00:00:00.000 --> ...` cue form."""
    transcript = ParsedTranscript(had_timestamps=True)
    normalized = content.replace("\r\n", "\n").replace("\r", "\n")
    for block in re.split(r"\n\s*\n", normalized):
        lines = [ln for ln in block.split("\n") if ln.strip()]
        if not lines:
            continue
        cue_line_index = next((i for i, ln in enumerate(lines) if _CUE_RE.search(ln)), None)
        if cue_line_index is None:
            continue
        cue = _CUE_RE.search(lines[cue_line_index])
        if cue is None:
            continue
        g = cue.groups()
        start = _to_seconds(g[0], g[1], g[2], g[3])
        end = _to_seconds(g[4], g[5], g[6], g[7])
        text = " ".join(lines[cue_line_index + 1 :]).strip()
        if not text:
            continue
        text, speaker = _clean_cue_text(text)
        if not text:
            continue
        transcript.segments.append(RawSegment(text=text, start=start, end=end, speaker=speaker))
    return transcript


def split_sentences(text: str) -> list[str]:
    """Lightweight sentence splitter (no NLTK download required)."""
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return []
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9\"'(])", text)
    return [p.strip() for p in parts if p.strip()]


def parse_plain_text(content: str) -> ParsedTranscript:
    """Plain text: one segment per sentence. Optional `Speaker: text` prefixes
    are honoured. No timestamps exist in the source, so none are produced."""
    transcript = ParsedTranscript(had_timestamps=False)
    for line in content.replace("\r\n", "\n").split("\n"):
        line = line.strip()
        if not line:
            continue
        speaker: str | None = None
        text = line
        match = _SPEAKER_LINE_RE.match(line)
        if match and 0 < len(match.group(1).split()) <= 4:
            speaker = match.group(1).strip()
            text = match.group(2).strip()
        for sentence in split_sentences(text):
            transcript.segments.append(RawSegment(text=sentence, speaker=speaker))
    return transcript


def load_transcript(path: str) -> ParsedTranscript:
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        raw = fh.read()
    if "-->" in raw:
        parsed = parse_vtt_or_srt(raw)
        if parsed.segments:
            return parsed
    return parse_plain_text(raw)
