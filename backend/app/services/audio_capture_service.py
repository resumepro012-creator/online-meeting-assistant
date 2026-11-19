
"""Continuous system-audio capture for meeting recordings."""

from __future__ import annotations

import logging
import re
import threading
import uuid
import wave
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import soundcard as sc

from app.core.config import settings

logger = logging.getLogger(__name__)

SAMPLE_RATE = 16_000
CHUNK_SECONDS = 1
START_TIMEOUT_SECONDS = 15
STOP_TIMEOUT_SECONDS = 10


class RecordingError(RuntimeError):
    """Raised when an audio recording cannot start or stop safely."""


@dataclass
class RecordingSession:
    user_id: str
    course_id: str
    file_path: Path
    stop_event: threading.Event = field(default_factory=threading.Event)
    ready_event: threading.Event = field(default_factory=threading.Event)
    thread: threading.Thread | None = None
    error: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    frames_written: int = 0
    channels: int = 0


class AudioCaptureService:
    """Allows one continuous system-audio recording at a time."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._session: RecordingSession | None = None

    def start_recording(self, user_id: str, course_id: str) -> dict:
        """Start capturing the default Windows output device."""

        with self._lock:
            if self._session is not None:
                raise RecordingError(
                    "A recording session is already active or awaiting cleanup."
                )

            safe_course_id = re.sub(r"[^A-Za-z0-9_-]", "_", course_id)
            recording_dir = Path(settings.upload_dir) / safe_course_id
            recording_dir.mkdir(parents=True, exist_ok=True)

            filename = f"meeting_recording_{uuid.uuid4().hex}.wav"
            file_path = recording_dir / filename

            session = RecordingSession(
                user_id=user_id,
                course_id=course_id,
                file_path=file_path,
            )

            session.thread = threading.Thread(
                target=self._capture_worker,
                args=(session,),
                name="meeting-audio-capture",
                daemon=True,
            )

            self._session = session
            session.thread.start()

        # Wait until the worker has opened the audio device and WAV file.
        if not session.ready_event.wait(START_TIMEOUT_SECONDS):
            session.stop_event.set()
            session.thread.join(timeout=STOP_TIMEOUT_SECONDS)
            with self._lock:
                if self._session is session and not session.thread.is_alive():
                    self._session = None
            raise RecordingError("Audio recording did not initialize in time.")

        if session.error:
            session.thread.join(timeout=STOP_TIMEOUT_SECONDS)
            with self._lock:
                if self._session is session and not session.thread.is_alive():
                    self._session = None
            raise RecordingError(session.error)

        return {
            "message": "Audio recording started.",
            "course_id": course_id,
            "device": session.device_name,
            "started_at": session.started_at.isoformat(),
        }

    def stop_recording(self, user_id: str) -> dict:
        """Stop capture and wait for the WAV file to be finalized."""

        with self._lock:
            session = self._session

            if session is None:
                raise RecordingError("There is no active recording.")

            if session.user_id != user_id:
                raise RecordingError("This recording belongs to another user.")

            session.stop_event.set()
            thread = session.thread

        if thread is not None:
            thread.join(timeout=STOP_TIMEOUT_SECONDS)

            if thread.is_alive():
                raise RecordingError(
                    "Recording is still stopping. The WAV file is not ready yet."
                )

        with self._lock:
            if self._session is session:
                self._session = None

        if session.error:
            raise RecordingError(session.error)

        if not session.file_path.exists():
            raise RecordingError("The recording WAV file was not created.")

        with wave.open(str(session.file_path), "rb") as wav:
            duration = wav.getnframes() / wav.getframerate()
            channels = wav.getnchannels()
            sample_rate = wav.getframerate()

        if duration <= 0:
            raise RecordingError("The recording contains no audio frames.")

        session.finished_at = datetime.now(timezone.utc)

        return {
            "message": "Recording stopped and WAV file finalized.",
            "course_id": session.course_id,
            "file_path": str(session.file_path),
            "duration_seconds": round(duration, 2),
            "channels": channels,
            "sample_rate": sample_rate,
            "file_size_bytes": session.file_path.stat().st_size,
            "finished_at": session.finished_at.isoformat(),
        }

    def _capture_worker(self, session: RecordingSession) -> None:
        """Capture audio in a dedicated thread and write PCM16 WAV."""

        try:
            speaker = sc.default_speaker()
            session.device_name = speaker.name

            loopback = sc.get_microphone(
                id=str(speaker.name),
                include_loopback=True,
            )

            with wave.open(str(session.file_path), "wb") as wav:
                first_chunk = True

                while not session.stop_event.is_set():
                    audio = loopback.record(
                        samplerate=SAMPLE_RATE,
                        numframes=SAMPLE_RATE * CHUNK_SECONDS,
                    )

                    audio = np.asarray(audio, dtype=np.float32)

                    if audio.ndim == 1:
                        audio = audio.reshape(-1, 1)

                    if audio.size == 0:
                        continue

                    # Convert stereo system audio to mono.
                    if audio.shape[1] > 1:
                        audio = np.mean(audio, axis=1, keepdims=True)

                    if first_chunk:
                        session.channels = audio.shape[1]
                        wav.setnchannels(session.channels)
                        wav.setsampwidth(2)
                        wav.setframerate(SAMPLE_RATE)
                        session.started_at = datetime.now(timezone.utc)
                        first_chunk = False
                        session.ready_event.set()

                    pcm_audio = (
                        np.clip(audio, -1.0, 1.0) * 32767
                    ).astype("<i2")

                    wav.writeframes(pcm_audio.tobytes())
                    session.frames_written += len(audio)

            logger.info(
                "Audio recording finalized: %s (%s frames)",
                session.file_path,
                session.frames_written,
            )

        except Exception as exc:
            session.error = f"Audio capture failed: {exc}"
            logger.exception(session.error)

        finally:
            session.ready_event.set()


audio_capture_service = AudioCaptureService()
