"""Transcription via Whisper on Modal."""

import base64
import os

import httpx


WHISPER_URL = os.environ.get(
    "MODAL_WHISPER_URL",
    "https://anubhavbharadwaaj--slugvoice-whisper-whisperserver-api.modal.run",
)


def transcribe_audio(audio_path: str) -> str:
    """Transcribe audio using Whisper on Modal."""
    with open(audio_path, "rb") as f:
        audio_b64 = base64.b64encode(f.read()).decode()

    resp = httpx.post(
        WHISPER_URL,
        json={"audio": audio_b64},
        timeout=120,
    )
    resp.raise_for_status()
    return resp.json()["text"]
