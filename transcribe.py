"""Transcription via Whisper on Modal."""

import base64
import os
from pathlib import Path

import httpx


WHISPER_URL = os.environ.get(
    "MODAL_WHISPER_URL",
    "https://anubhavbharadwaaj--slugvoice-whisper-whisperserver-api.modal.run",
)
_HERE = Path(__file__).resolve().parent
_SAMPLE_AUDIO = _HERE / "sample_session.wav"


def _resolve_audio_path(audio_path: str) -> Path:
    """Return a stable audio path, tolerating evicted Gradio example temp files."""
    path = Path(audio_path)
    if path.exists():
        return path

    name = path.name.lower()
    if name.startswith("sample_session") and _SAMPLE_AUDIO.exists():
        return _SAMPLE_AUDIO

    raise FileNotFoundError(
        f"Audio file is no longer available: {audio_path}. "
        "Please re-upload the file and try again."
    )


def transcribe_audio(audio_path: str) -> str:
    """Transcribe audio using Whisper on Modal."""
    resolved_path = _resolve_audio_path(audio_path)
    with open(resolved_path, "rb") as f:
        audio_b64 = base64.b64encode(f.read()).decode()

    resp = httpx.post(
        WHISPER_URL,
        json={"audio": audio_b64},
        timeout=120,
    )
    resp.raise_for_status()
    return resp.json()["text"]
