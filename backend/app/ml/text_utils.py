"""Shared text helpers: tokenisation, stopwords, keyword scoring.

Standard-library only — no NLTK/spaCy corpus download needed for the baseline.
"""

from __future__ import annotations

import re
from collections import Counter

STOPWORDS = {
    "a", "about", "above", "after", "again", "all", "also", "am", "an", "and", "any", "are",
    "as", "at", "be", "because", "been", "before", "being", "below", "between", "both", "but",
    "by", "can", "cannot", "could", "did", "do", "does", "doing", "don", "down", "during",
    "each", "few", "for", "from", "further", "get", "got", "had", "has", "have", "having",
    "he", "her", "here", "hers", "him", "his", "how", "i", "if", "in", "into", "is", "it",
    "its", "just", "let", "like", "me", "more", "most", "my", "no", "nor", "not", "now",
    "of", "off", "on", "once", "only", "or", "other", "our", "out", "over", "own", "really",
    "same", "she", "should", "so", "some", "such", "than", "that", "the", "their", "them",
    "then", "there", "these", "they", "this", "those", "through", "to", "too", "under",
    "until", "up", "very", "was", "we", "were", "what", "when", "where", "which", "while",
    "who", "whom", "why", "will", "with", "would", "you", "your", "yours", "okay", "ok",
    "right", "well", "going", "know", "see", "think", "want", "one", "two", "three", "yes",
    "yeah", "thing", "things", "make", "made", "take", "say", "said", "much", "many", "us",
}

_WORD_RE = re.compile(r"[A-Za-z][A-Za-z'\-]+")
_SENTENCE_END = re.compile(r"[.!?]$")


def tokenize(text: str) -> list[str]:
    return [m.group(0).lower() for m in _WORD_RE.finditer(text)]


def content_words(text: str) -> list[str]:
    return [w for w in tokenize(text) if w not in STOPWORDS and len(w) > 2]


def keyword_frequencies(text: str) -> Counter[str]:
    return Counter(content_words(text))


def title_case(word: str) -> str:
    return word[:1].upper() + word[1:]


def is_question(text: str) -> bool:
    stripped = text.strip()
    if stripped.endswith("?"):
        return True
    first = tokenize(stripped)
    if not first:
        return False
    return first[0] in {
        "what", "why", "how", "which", "when", "who", "whom", "where", "whose",
        "is", "are", "was", "were", "do", "does", "did", "can", "could", "should",
        "would", "will", "may", "might",
    }


def sentences(text: str) -> list[str]:
    from app.ml.transcript_io import split_sentences

    return split_sentences(text)


def normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()
