"""Speech-to-text.

Two supported inputs, both honest about what they actually did:

1. **Transcript upload** (.txt/.vtt/.srt) — parsed directly, no speech model
   involved. Method is reported as `transcript-parser`.
2. **Audio upload** — needs a real ASR model. `faster-whisper` is used when it
   is installed (see `backend/requirements-ml.txt`); the model runs locally on
   CPU. No cloud API is called, so there is no per-minute cost and no audio
   leaves the machine.

If audio is uploaded but no ASR library is installed, processing FAILS with an
explicit error. It is never silently replaced with placeholder text.

Model sizes and first-use download (faster-whisper, CTranslate2 int8 on CPU):

    tiny   ~75 MB    fastest, lowest accuracy
    base   ~142 MB   default here; good balance for clear lecture audio
    small  ~466 MB   noticeably better on noisy audio
    medium ~1.5 GB   slow on CPU
    large-v3 ~3 GB   requires a GPU for practical use

Weights are downloaded once on first use and cached (HF_HOME), then reused
offline. Timestamps come from the model's segment output.
"""

from __future__ import annotations

import importlib.util
import logging
import wave
from dataclasses import dataclass, field
from pathlib import Path

from app.core.config import settings
from app.ml.transcript_io import ParsedTranscript, RawSegment, load_transcript

logger = logging.getLogger(__name__)

AUDIO_EXTENSIONS = {".mp3", ".wav", ".m4a", ".mp4", ".webm", ".ogg", ".flac", ".aac", ".wma", ".mkv"}
TRANSCRIPT_EXTENSIONS = {".txt", ".vtt", ".srt"}


class SpeechToTextUnavailable(RuntimeError):
    """Raised when audio was supplied but no real ASR model is available."""


class UnsupportedAudioError(ValueError):
    """Raised when the uploaded file cannot be processed."""


@dataclass
class TranscriptionResult:
    segments: list[RawSegment] = field(default_factory=list)
    method: str = "unknown"
    had_timestamps: bool = False
    duration_seconds: float | None = None
    language: str | None = None


def faster_whisper_available() -> bool:
    return importlib.util.find_spec("faster_whisper") is not None


def probe_duration_seconds(path: Path) -> float | None:
    """Best-effort duration for uncompressed WAV. None when it cannot be read
    without an extra dependency (reported as unknown, not guessed)."""
    if path.suffix.lower() != ".wav":
        return None
    try:
        with wave.open(str(path), "rb") as wav:
            frames, rate = wav.getnframes(), wav.getframerate()
            return round(frames / float(rate), 2) if rate else None
    except (wave.Error, OSError):
        return None


def validate_upload(path: Path, size_bytes: int) -> str:
    """Returns `transcript` or `audio`. Raises on anything unusable."""
    if size_bytes <= 0:
        raise UnsupportedAudioError("The uploaded file is empty.")
    if size_bytes > settings.max_upload_bytes:
        raise UnsupportedAudioError(
            f"File is larger than the {settings.max_upload_mb} MB limit "
            f"(got {size_bytes / (1024 * 1024):.1f} MB)."
        )

    suffix = path.suffix.lower()
    if suffix in TRANSCRIPT_EXTENSIONS:
        return "transcript"
    if suffix in AUDIO_EXTENSIONS:
        if size_bytes < 2048:
            raise UnsupportedAudioError(
                "The audio file is too small to contain speech — it may be silent or truncated."
            )
        return "audio"
    raise UnsupportedAudioError(
        f"Unsupported file type '{suffix}'. Supported audio: "
        f"{', '.join(sorted(AUDIO_EXTENSIONS))}. Supported transcripts: "
        f"{', '.join(sorted(TRANSCRIPT_EXTENSIONS))}."
    )


def transcribe_audio(path: Path) -> TranscriptionResult:
    """Runs local ASR. Raises SpeechToTextUnavailable if no model is installed."""
    backend = settings.stt_backend.lower()
    if backend == "baseline":
        raise SpeechToTextUnavailable(
            "Speech-to-text is disabled (STT_BACKEND=baseline). Upload a "
            ".txt/.vtt/.srt transcript, or set STT_BACKEND=auto and install "
            "backend/requirements-ml.txt."
        )
    if not faster_whisper_available():
        raise SpeechToTextUnavailable(
            "Audio processing needs a speech-to-text model, which is not installed. "
            "Install it with:\n"
            "    .venv\\Scripts\\python.exe -m pip install -r requirements-ml.txt\n"
            "or upload a .txt/.vtt/.srt transcript instead. "
            "(No transcription was attempted, so no results were produced.)"
        )
    return _transcribe_with_faster_whisper(path)


def _transcribe_with_faster_whisper(path: Path) -> TranscriptionResult:
    from faster_whisper import WhisperModel  # imported lazily: heavy dependency

    model_size = settings.whisper_model
    logger.info("Loading faster-whisper model '%s' (first run downloads weights)…", model_size)
    model = WhisperModel(model_size, device="cpu", compute_type="int8")

    logger.info("Transcribing %s", path.name)
    raw_segments, info = model.transcribe(
        str(path),
        beam_size=5,
        vad_filter=True,  # skip silence so empty recordings produce no segments
        vad_parameters={"min_silence_duration_ms": 700},
    )

    segments: list[RawSegment] = []
    for seg in raw_segments:
        text = (seg.text or "").strip()
        if not text:
            continue
        segments.append(RawSegment(text=text, start=float(seg.start), end=float(seg.end)))

    duration = getattr(info, "duration", None)
    return TranscriptionResult(
        segments=segments,
        method=f"faster-whisper:{model_size}",
        had_timestamps=True,
        duration_seconds=float(duration) if duration else None,
        language=getattr(info, "language", None),
    )


def obtain_transcript(path: Path, kind: str) -> TranscriptionResult:
    """Single entry point used by the pipeline."""
    if kind == "transcript":
        parsed: ParsedTranscript = load_transcript(str(path))
        return TranscriptionResult(
            segments=parsed.segments,
            method="transcript-parser",
            had_timestamps=parsed.had_timestamps,
        )
    result = transcribe_audio(path)
    if result.duration_seconds is None:
        result.duration_seconds = probe_duration_seconds(path)
    return result
