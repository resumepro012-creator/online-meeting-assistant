"""Health/readiness endpoint.

Reports which ML implementations are actually available, so the UI and the
project report can state facts instead of assumptions.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.ml.classifier import RuleBasedClassifier, get_classifier, transformers_available
from app.ml.stt import faster_whisper_available

router = APIRouter(tags=["health"])


@router.get("/health")
def health(db: Session = Depends(get_db)) -> dict:
    try:
        db.execute(text("SELECT 1"))
        database = "ok"
    except Exception as exc:  # noqa: BLE001
        database = f"error: {exc}"

    classifier = get_classifier()
    return {
        "status": "ok" if database == "ok" else "degraded",
        "database": database,
        "pipeline": {
            "speechToText": {
                "available": faster_whisper_available(),
                "backend": settings.stt_backend,
                "model": settings.whisper_model if faster_whisper_available() else None,
                "note": (
                    "faster-whisper installed — audio uploads are transcribed locally."
                    if faster_whisper_available()
                    else "faster-whisper NOT installed — upload a .txt/.vtt/.srt transcript, "
                    "or install backend/requirements-ml.txt to transcribe audio."
                ),
            },
            "segmentClassifier": {
                "method": classifier.method,
                "isRealModel": not isinstance(classifier, RuleBasedClassifier),
                "transformersInstalled": transformers_available(),
                "backend": settings.segment_classifier_backend,
            },
            "summarizer": {"backend": settings.summarizer_backend},
        },
    }
