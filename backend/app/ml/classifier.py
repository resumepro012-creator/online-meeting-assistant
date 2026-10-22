"""Transcript-segment classification — the deep-learning component of the project.

Target labels (agreed with the project brief):

    QUESTION | INFORMATION | DISCUSSION | DECISION | ACTION_ITEM

Two interchangeable implementations sit behind one interface:

* ``TransformerSegmentClassifier`` — zero-shot classification with a pretrained
  NLI transformer (default ``typeform/distilbert-base-uncased-mnli``, ~268 MB,
  runs on CPU). No fine-tuning is required to get started; this is the intended
  "real model" path and is what Phase 6 evaluation runs against.
* ``RuleBasedClassifier`` — a deterministic keyword/pattern baseline. It exists
  so the end-to-end pipeline, progress reporting and storage can be tested
  without a model download, and so the report can quote a real baseline number.

The active implementation is selected by ``SEGMENT_CLASSIFIER_BACKEND``
(auto | real | baseline) and is always recorded on every prediction, so a result
produced by the baseline can never be mistaken for a model output.

Nothing here invents labels: if neither implementation can run, the pipeline
fails with an explicit error instead of writing fabricated results.
"""

from __future__ import annotations

import importlib.util
import logging
import re
from dataclasses import dataclass, field
from typing import Protocol

from app.core.config import settings

logger = logging.getLogger(__name__)

LABELS: tuple[str, ...] = ("QUESTION", "INFORMATION", "DISCUSSION", "DECISION", "ACTION_ITEM")

# Human-readable descriptions used as the zero-shot hypothesis targets.
ZERO_SHOT_LABEL_NAMES: dict[str, str] = {
    "QUESTION": "a question asked by a participant",
    "INFORMATION": "an explanation or factual statement by the presenter",
    "DISCUSSION": "an open discussion or exchange of opinions",
    "DECISION": "a decision that has been made",
    "ACTION_ITEM": "a task or instruction someone is asked to carry out",
}

DEFAULT_ZERO_SHOT_MODEL = "typeform/distilbert-base-uncased-mnli"


@dataclass
class Prediction:
    label: str
    confidence: float
    scores: dict[str, float] = field(default_factory=dict)
    method: str = "unknown"


class SegmentClassifier(Protocol):
    method: str

    def classify(self, texts: list[str]) -> list[Prediction]: ...


# --------------------------------------------------------------------------- #
# Baseline: deterministic pattern scoring
# --------------------------------------------------------------------------- #
def _W(alternation: str) -> re.Pattern[str]:
    """Compiles a ``|``-separated list of literal phrases into one word-bounded pattern."""
    parts = [part.strip() for part in alternation.split("|") if part.strip()]
    return re.compile(r"\b(?:" + "|".join(re.escape(part) for part in parts) + r")\b", re.IGNORECASE)

_QUESTION_STARTERS = re.compile(
    r"^(what|why|how|which|when|who|whom|where|whose|is|are|was|were|do|does|did|can|could|"
    r"should|would|will|may|might|any)\b",
    re.IGNORECASE,
)

# (pattern, weight) per label. Weights are hand-tuned on the labelled dev
# samples in backend/tests/data; they are not claimed to be optimal.
_PATTERNS: dict[str, list[tuple[re.Pattern[str], float]]] = {
    "QUESTION": [
        (re.compile(r"\?\s*$"), 3.0),
        (_QUESTION_STARTERS, 2.0),
        (_W("can you|could you|would you|any questions|does anyone|what about|"
            "how do we|how does|is it possible|do you know|do we need"), 1.5),
    ],
    "INFORMATION": [
        (_W("is defined as|refers to|is called|consists of|means that|is a|are a|"
            "is the|are the|is an"), 1.5),
        (_W("for example|for instance|such as|note that|remember that|in other words|"
            "because of|the reason"), 1.2),
        (re.compile(r"\b\d+(\.\d+)?\s*(%|percent|ms|mb|gb|layers|parameters|dimensions)\b", re.I), 0.8),
    ],
    "DISCUSSION": [
        (_W("let's discuss|let us discuss|think about|in my opinion|from my perspective|"
            "some people|on the other hand|any thoughts|what do you think|let's compare|"
            "let us compare|difference between|debate"), 2.2),
        (_W("however|but then|might be|it depends|in general"), 0.8),
    ],
    "DECISION": [
        (_W("we will|we'll|we have decided|we decided|let's go with|let us go with|"
            "we are going to|we agreed|has been decided|the final decision|final answer|"
            "we settle on|we'll use|we will use|it is settled"), 2.6),
        (_W("conclusion|conclusion is|so the plan is|we are sticking with"), 1.2),
    ],
    "ACTION_ITEM": [
        (_W("please|make sure|don't forget|do not forget|remember to|you need to|"
            "you should|you must|be sure to|submit|submission|hand in|deadline|due by|"
            "due on|by next|for next class|before the next class|complete the|"
            "read chapter|upload|revise|prepare"), 2.6),
        (re.compile(
            r"^(submit|read|complete|review|prepare|install|implement|check|watch|solve|"
            r"finish|send|upload|revise|study|write)\b",
            re.IGNORECASE,
        ), 1.5),
    ],
}

# Declarative statements are the most common segment type, so a small prior
# keeps unlabelled material out of the rarer classes.
_INFORMATION_PRIOR = 1.0
_EPSILON = 1e-6


class RuleBasedClassifier:
    """Deterministic baseline. Method string is recorded on every prediction."""

    method = "baseline-pattern-v1"

    def classify(self, texts: list[str]) -> list[Prediction]:
        return [self._classify_one(t) for t in texts]

    def _classify_one(self, text: str) -> Prediction:
        scores: dict[str, float] = {label: 0.0 for label in LABELS}
        matched = False

        for label, patterns in _PATTERNS.items():
            for pattern, weight in patterns:
                if pattern.search(text):
                    scores[label] += weight
                    matched = True

        if not matched:
            # No signal at all: report the prior as a weak, uniform guess instead
            # of pretending the text confidently belongs to `INFORMATION`.
            uniform = round(1 / len(LABELS), 4)
            return Prediction(
                label="INFORMATION",
                confidence=uniform,
                scores={label: uniform for label in LABELS},
                method=self.method,
            )

        scores["INFORMATION"] += _INFORMATION_PRIOR
        total = sum(scores.values()) + _EPSILON
        normalised = {label: round(value / total, 4) for label, value in scores.items()}
        best_label = max(normalised, key=lambda k: normalised[k])
        return Prediction(
            label=best_label,
            confidence=normalised[best_label],
            scores=normalised,
            method=self.method,
        )


# --------------------------------------------------------------------------- #
# Real model: zero-shot NLI transformer
# --------------------------------------------------------------------------- #
def transformers_available() -> bool:
    return importlib.util.find_spec("transformers") is not None and (
        importlib.util.find_spec("torch") is not None
    )


class TransformerSegmentClassifier:
    """Zero-shot classification with a pretrained MNLI model (CPU, no fine-tuning)."""

    def __init__(self, model_name: str = DEFAULT_ZERO_SHOT_MODEL) -> None:
        from transformers import pipeline  # lazy: heavy dependency

        self.model_name = model_name
        self.method = f"zero-shot:{model_name}"
        logger.info("Loading zero-shot classifier '%s' (first run downloads weights)…", model_name)
        self._pipeline = pipeline(
            "zero-shot-classification",
            model=model_name,
            device=-1,  # CPU
        )

    def classify(self, texts: list[str]) -> list[Prediction]:
        if not texts:
            return []
        candidate_labels = [ZERO_SHOT_LABEL_NAMES[label] for label in LABELS]
        results = self._pipeline(
            texts,
            candidate_labels=candidate_labels,
            hypothesis_template="This segment is {}.",
            batch_size=16,
        )
        if isinstance(results, dict):  # pipeline returns a dict for a single input
            results = [results]

        predictions: list[Prediction] = []
        for result in results:
            raw_scores = dict(zip(result["labels"], result["scores"], strict=False))
            # Map the human-readable hypothesis labels back to our enum.
            scores = {
                label: round(float(raw_scores.get(name, 0.0)), 4)
                for label, name in ZERO_SHOT_LABEL_NAMES.items()
            }
            best_label = max(scores, key=lambda k: scores[k])
            predictions.append(
                Prediction(
                    label=best_label,
                    confidence=scores[best_label],
                    scores=scores,
                    method=self.method,
                )
            )
        return predictions


# --------------------------------------------------------------------------- #
# Selection
# --------------------------------------------------------------------------- #
_classifier_cache: SegmentClassifier | None = None


class ClassifierUnavailable(RuntimeError):
    """Raised when a real classifier was required but could not be loaded."""


def get_classifier() -> SegmentClassifier:
    """Resolves the configured classifier once and caches it for the process."""
    global _classifier_cache
    if _classifier_cache is not None:
        return _classifier_cache

    backend = settings.segment_classifier_backend.lower()
    if backend == "baseline":
        _classifier_cache = RuleBasedClassifier()
        return _classifier_cache

    if transformers_available():
        try:
            _classifier_cache = TransformerSegmentClassifier()
            return _classifier_cache
        except Exception as exc:  # noqa: BLE001 - fall back only in "auto" mode
            if backend == "real":
                raise ClassifierUnavailable(
                    f"Could not load the transformer classifier: {exc}"
                ) from exc
            logger.warning(
                "Transformer classifier unavailable (%s). Falling back to the "
                "pattern baseline — predictions will be labelled '%s'.",
                exc,
                RuleBasedClassifier.method,
            )
    elif backend == "real":
        raise ClassifierUnavailable(
            "SEGMENT_CLASSIFIER_BACKEND=real but transformers/torch are not installed. "
            "Install them with: .venv\\Scripts\\python.exe -m pip install -r requirements-ml.txt"
        )
    else:
        logger.info(
            "transformers/torch not installed — using the pattern baseline (%s).",
            RuleBasedClassifier.method,
        )

    _classifier_cache = RuleBasedClassifier()
    return _classifier_cache
