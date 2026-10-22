"""Lecture summary + structured notes generation.

Default implementation is **extractive**: every sentence in the summary and the
notes is taken verbatim from the transcript, so the output cannot contain
hallucinated content. An optional **abstractive** transformer summary
(``sshleifer/distilbart-cnn-6-6``) can be enabled, which paraphrases and is
therefore labelled as such in the API response.

Both implementations are grounded in what was actually said; neither invents
topics that do not appear in the transcript.
"""

from __future__ import annotations

import importlib.util
import logging
import math
import re
from collections import Counter
from dataclasses import dataclass, field

from app.core.config import settings
from app.ml.text_utils import STOPWORDS, content_words, title_case
from app.ml.types import PipelineSegment

logger = logging.getLogger(__name__)

EXTRACTIVE_METHOD = "extractive-textrank-lite-v1"
ABSTRACTIVE_MODEL = "sshleifer/distilbart-cnn-6-6"

_DEFINITION = re.compile(
    r"\b(is defined as|refers to|is called|means that|is a kind of|consists of|"
    r"is essentially|is basically|you can think of|is used for|stands for)\b",
    re.IGNORECASE,
)
_IMPORTANCE = re.compile(
    r"\b(important|key|main|critical|remember|note that|in summary|to summarize|"
    r"the point is|first|second|finally|for example)\b",
    re.IGNORECASE,
)
_WORD = re.compile(r"[A-Za-z][A-Za-z'\-]+")


@dataclass
class GeneratedNote:
    summary: str
    preview: str
    topics: list[str] = field(default_factory=list)
    sections: list[dict] = field(default_factory=list)
    method: str = EXTRACTIVE_METHOD


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def _usable_sentences(segments: list[PipelineSegment]) -> list[tuple[int, str]]:
    """(position, text) pairs — cleaned, deduplicated, questions removed."""
    seen: set[str] = set()
    result: list[tuple[int, str]] = []
    for position, seg in enumerate(segments):
        text = re.sub(r"\s+", " ", seg.text).strip()
        if len(text) < 25 or len(_WORD.findall(text)) < 5:
            continue
        if seg.category == "QUESTION":
            continue
        key = re.sub(r"[^a-z ]", "", text.lower())
        if key in seen:
            continue
        seen.add(key)
        result.append((position, text))
    return result


def _score_sentences(sentences: list[tuple[int, str]], frequencies: Counter[str]) -> list[float]:
    max_freq = max(frequencies.values()) if frequencies else 1
    scores: list[float] = []
    total = max(len(sentences), 1)
    for position, (index, text) in enumerate(sentences):
        words = content_words(text)
        if not words:
            scores.append(0.0)
            continue
        lexical = sum(frequencies[w] / max_freq for w in words) / math.sqrt(len(words))
        position_bonus = 1.0 + 0.35 * (1 - position / total)  # earlier = slightly more central
        style_bonus = 0.25 * bool(_DEFINITION.search(text)) + 0.15 * bool(_IMPORTANCE.search(text))
        scores.append(lexical * position_bonus + style_bonus)
    return scores


def _top_phrases(text: str, limit: int = 6) -> list[str]:
    words = content_words(text)
    unigrams = Counter(words)
    bigrams = Counter(zip(words, words[1:], strict=False))
    bigram_totals = Counter({f"{a} {b}": c for (a, b), c in bigrams.items() if c >= 2})

    chosen: list[str] = []
    used_words: set[str] = set()
    for phrase, _count in bigram_totals.most_common(limit):
        first, second = phrase.split()
        if first in used_words or second in used_words:
            continue
        chosen.append(phrase)
        used_words.update((first, second))
        if len(chosen) >= 2:  # at most two multi-word phrases, they crowd out the rest
            break

    for word, _count in unigrams.most_common(limit * 3):
        if len(chosen) >= limit:
            break
        if word in used_words:
            continue
        chosen.append(word)
        used_words.add(word)

    return [title_case(p) for p in chosen]


def _build_sections(
    sentences: list[tuple[int, str]], scores: list[float], topics: list[str], questions: list[str]
) -> list[dict]:
    ranked = sorted(zip(sentences, scores, strict=False), key=lambda pair: pair[1], reverse=True)
    used: set[str] = set()
    sections: list[dict] = []

    # 1. Key concepts — definition-style statements first.
    concepts = [text for _pos, text in sentences if _DEFINITION.search(text)][:5]
    if not concepts:
        concepts = [text for (_pos, text), _score in ranked[:3]]
    if concepts:
        used.update(concepts)
        sections.append({"heading": "Key Concepts", "points": concepts})

    # 2. Main points — highest scoring material not already shown.
    main_points = [text for (_pos, text), _score in ranked if text not in used][:6]
    if main_points:
        used.update(main_points)
        sections.append({"heading": "Main Points", "points": main_points})

    # 3. One section per dominant topic that actually recurs.
    for topic in topics[:3]:
        needle = topic.lower()
        if " " in needle:
            matching = [text for _pos, text in sentences if needle in text.lower()]
        else:
            matching = [
                text
                for _pos, text in sentences
                if re.search(rf"\b{re.escape(needle[:-1] if needle.endswith('s') else needle)}\w*", text, re.I)
            ]
        matching = [text for text in matching if text not in used][:3]
        if len(matching) >= 2:
            used.update(matching)
            sections.append({"heading": f"About {topic}", "points": matching})

    # 4. Questions raised in the lecture (verbatim, kept separate from notes).
    if questions:
        sections.append({"heading": "Questions Raised in Class", "points": questions[:6]})

    return sections


def _make_preview(summary: str, limit: int = 220) -> str:
    if len(summary) <= limit:
        return summary
    return summary[:limit].rsplit(" ", 1)[0] + "…"


# --------------------------------------------------------------------------- #
# extractive baseline
# --------------------------------------------------------------------------- #
class ExtractiveSummarizer:
    method = EXTRACTIVE_METHOD

    def generate(self, segments: list[PipelineSegment], questions: list[str]) -> GeneratedNote:
        sentences = _usable_sentences(segments)
        if not sentences:
            return GeneratedNote(
                summary="", preview="", topics=[], sections=[], method=self.method
            )

        corpus = " ".join(text for _pos, text in sentences)
        frequencies = Counter(content_words(corpus))
        scores = _score_sentences(sentences, frequencies)

        count = min(max(3, len(sentences) // 8), 7)
        ranked = sorted(zip(sentences, scores, strict=False), key=lambda p: p[1], reverse=True)[:count]
        ordered = sorted(ranked, key=lambda p: p[0][0])
        summary = " ".join(text for (_pos, text), _score in ordered)

        topics = _top_phrases(corpus)
        sections = _build_sections(sentences, scores, topics, questions)
        return GeneratedNote(
            summary=summary,
            preview=_make_preview(summary),
            topics=topics,
            sections=sections,
            method=self.method,
        )


# --------------------------------------------------------------------------- #
# optional abstractive summarizer
# --------------------------------------------------------------------------- #
def transformers_available() -> bool:
    return importlib.util.find_spec("transformers") is not None and (
        importlib.util.find_spec("torch") is not None
    )


class AbstractiveSummarizer:
    """Paraphrasing summary. Faster and more fluent, but it can rephrase content,
    so the API marks it as abstractive and the extractive version stays available."""

    def __init__(self, model_name: str = ABSTRACTIVE_MODEL, fallback: ExtractiveSummarizer | None = None):
        from transformers import pipeline

        self.method = f"abstractive:{model_name}"
        self._fallback = fallback or ExtractiveSummarizer()
        logger.info("Loading summarization model '%s' (first run downloads weights)…", model_name)
        self._pipeline = pipeline("summarization", model=model_name, device=-1)

    def _chunks(self, text: str, size: int = 900) -> list[str]:
        words = text.split()
        return [" ".join(words[i : i + size]) for i in range(0, len(words), size)] or [text]

    def generate(self, segments: list[PipelineSegment], questions: list[str]) -> GeneratedNote:
        base = self._fallback.generate(segments, questions)  # topics/sections stay extractive
        sentences = _usable_sentences(segments)
        corpus = " ".join(text for _pos, text in sentences)
        if not corpus:
            return base

        try:
            parts: list[str] = []
            for chunk in self._chunks(corpus):
                words = len(chunk.split())
                out = self._pipeline(
                    chunk,
                    max_length=min(160, max(40, words // 2)),
                    min_length=min(40, max(20, words // 6)),
                    do_sample=False,
                    truncation=True,
                )
                parts.append(out[0]["summary_text"].strip())
            summary = " ".join(parts).strip()
        except Exception as exc:  # noqa: BLE001
            logger.warning("Abstractive summarisation failed (%s); using extractive summary.", exc)
            return base

        return GeneratedNote(
            summary=summary,
            preview=_make_preview(summary),
            topics=base.topics,
            sections=base.sections,
            method=self.method,
        )


# --------------------------------------------------------------------------- #
# selection
# --------------------------------------------------------------------------- #
_summarizer_cache: object | None = None


class SummarizerUnavailable(RuntimeError):
    pass


def get_summarizer():
    global _summarizer_cache
    if _summarizer_cache is not None:
        return _summarizer_cache

    backend = settings.summarizer_backend.lower()
    if backend == "baseline":
        _summarizer_cache = ExtractiveSummarizer()
        return _summarizer_cache

    if transformers_available():
        try:
            _summarizer_cache = AbstractiveSummarizer()
            return _summarizer_cache
        except Exception as exc:  # noqa: BLE001
            if backend == "real":
                raise SummarizerUnavailable(f"Could not load the summarisation model: {exc}") from exc
            logger.warning("Abstractive summariser unavailable (%s); using extractive.", exc)
    elif backend == "real":
        raise SummarizerUnavailable(
            "SUMMARIZER_BACKEND=real but transformers/torch are not installed. Install "
            "backend/requirements-ml.txt, or set SUMMARIZER_BACKEND=baseline."
        )

    _summarizer_cache = ExtractiveSummarizer()
    return _summarizer_cache


__all__ = [
    "ABSTRACTIVE_MODEL",
    "EXTRACTIVE_METHOD",
    "AbstractiveSummarizer",
    "ExtractiveSummarizer",
    "GeneratedNote",
    "STOPWORDS",
    "SummarizerUnavailable",
    "get_summarizer",
]
