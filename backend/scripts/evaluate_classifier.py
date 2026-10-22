"""Honest evaluation harness for the transcript-segment classifier.

This is the ONLY place in the project that reports a classification score. It
measures whichever implementation is actually active (the deterministic baseline
or the zero-shot Transformer) on the hand-labelled dev segments in
``tests/data/labelled_segments.jsonl`` and prints a real confusion matrix.

READ THIS BEFORE QUOTING THE NUMBERS IN A REPORT
------------------------------------------------
* The dev set is small and hand-authored for this project. It is a *development*
  set, not a benchmark, and it is the same material the baseline's patterns were
  tuned against. A high score here therefore proves internal consistency and
  regression safety — it does NOT establish generalisation.
* The label space is fixed and closed (5 labels). Nothing is inferred.
* If the baseline is active, the printed method string will say so. A baseline
  score must never be presented as a trained-model score.

Run:
    .venv\\Scripts\\python.exe scripts\\evaluate_classifier.py
    .venv\\Scripts\\python.exe scripts\\evaluate_classifier.py --backend real
    .venv\\Scripts\\python.exe scripts\\evaluate_classifier.py --json report.json

Exit code is 0 whenever the report was produced (it is a report, not a gate);
it is non-zero only if the dev set could not be read.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

DEFAULT_DATA = BACKEND_DIR / "tests" / "data" / "labelled_segments.jsonl"


def _load(path: Path) -> tuple[list[str], list[str]]:
    """Reads ``{"text": ..., "label": ...}`` lines, dropping anything malformed."""
    texts: list[str] = []
    labels: list[str] = []
    with path.open(encoding="utf-8") as handle:
        for lineno, line in enumerate(handle, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise SystemExit(f"{path}:{lineno} is not valid JSON: {exc}") from exc
            text, label = row.get("text"), row.get("label")
            if not isinstance(text, str) or not isinstance(label, str):
                raise SystemExit(f"{path}:{lineno} needs string 'text' and 'label' fields.")
            texts.append(text)
            labels.append(label.strip().upper())
    return texts, labels


def _metrics(
    truths: list[str], predicted: list[str], labels: tuple[str, ...]
) -> dict:
    """Accuracy + per-class precision/recall/F1/support and the confusion matrix."""
    total = len(truths)
    correct = sum(1 for t, p in zip(truths, predicted) if t == p)

    confusion = {actual: Counter() for actual in labels}
    for actual, guess in zip(truths, predicted):
        if actual in confusion:
            confusion[actual][guess] += 1

    per_class = {}
    for label in labels:
        tp = confusion[label].get(label, 0)
        support = sum(confusion[label].values())
        predicted_total = sum(confusion[a].get(label, 0) for a in labels)
        precision = tp / predicted_total if predicted_total else 0.0
        recall = tp / support if support else 0.0
        f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
        per_class[label] = {
            "precision": precision,
            "recall": recall,
            "f1": f1,
            "support": support,
        }

    scored = [per_class[label]["f1"] for label in labels if per_class[label]["support"]]
    macro_f1 = sum(scored) / len(scored) if scored else 0.0

    return {
        "total": total,
        "correct": correct,
        "accuracy": correct / total if total else 0.0,
        "macro_f1": macro_f1,
        "per_class": per_class,
        "confusion": {a: dict(sorted(confusion[a].items())) for a in labels},
    }


def _print_report(method: str, labels: tuple[str, ...], result: dict) -> None:
    print("=" * 72)
    print("SEGMENT CLASSIFIER - EVALUATION REPORT")
    print("=" * 72)
    print(f"method            : {method}")
    print("data              : tests/data/labelled_segments.jsonl (hand-labelled dev set)")
    print(f"segments evaluated: {result['total']}")
    print()
    print(f"accuracy          : {result['accuracy']:.4f}  ({result['correct']}/{result['total']})")
    print(f"macro F1          : {result['macro_f1']:.4f}")
    print()
    print("per class:")
    print(f"  {'label':<14}{'precision':>10}{'recall':>10}{'f1':>10}{'support':>9}")
    for label in labels:
        row = result["per_class"][label]
        print(
            f"  {label:<14}{row['precision']:>10.3f}{row['recall']:>10.3f}"
            f"{row['f1']:>10.3f}{row['support']:>9}"
        )
    print()
    print("confusion matrix (rows = truth, columns = predicted):")
    header = "".join(f"{label[:9]:>10}" for label in labels)
    print(f"  {'':<14}{header}")
    for actual in labels:
        cells = "".join(f"{result['confusion'][actual].get(g, 0):>10}" for g in labels)
        print(f"  {actual:<14}{cells}")
    print()
    print("CAVEAT: small hand-authored dev set, not a benchmark. Report this number")
    print("with the method string above so a baseline score is never read as a")
    print("trained-model score.")


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate the active segment classifier.")
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA, help="Path to a JSONL dev set.")
    parser.add_argument(
        "--backend",
        choices=["auto", "real", "baseline"],
        default=None,
        help="Override SEGMENT_CLASSIFIER_BACKEND for this run only.",
    )
    parser.add_argument("--json", type=Path, default=None, help="Also write the report as JSON.")
    args = parser.parse_args()

    if args.backend:
        # Must be set before `app.core.config` is imported for the override to stick.
        import os

        os.environ["SEGMENT_CLASSIFIER_BACKEND"] = args.backend

    # Imported here (not at module top) so --backend takes effect.
    from app.ml.classifier import LABELS, ClassifierUnavailable, get_classifier

    if not args.data.exists():
        print(f"FAIL: dev set not found at {args.data}")
        return 1

    texts, truths = _load(args.data)
    unknown = sorted({label for label in truths if label not in LABELS})
    if unknown:
        print(f"FAIL: dev set contains labels outside the model's label space: {unknown}")
        print(f"      model labels: {list(LABELS)}")
        return 1

    try:
        classifier = get_classifier()
    except ClassifierUnavailable as exc:
        # No score is printed: better to report "not available" than to silently
        # evaluate the baseline and let it be quoted as the model's score.
        print(f"FAIL: the requested classifier is not available.\n  {exc}")
        return 1

    predictions = classifier.classify(texts)
    predicted = [p.label for p in predictions]

    result = _metrics(truths, predicted, LABELS)
    _print_report(classifier.method, LABELS, result)

    if args.json:
        payload = {
            "method": classifier.method,
            "data": str(args.data.name),
            "caveat": "small hand-authored dev set, not a benchmark",
            **result,
        }
        args.json.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(f"\nJSON report written to {args.json}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
