"""Audio transcription utilities for TurboSkillSlug."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from huggingface_hub import InferenceClient


MODEL_NAME = "openai/whisper-small"
HF_TOKEN_ENV_VAR = "HF_TOKEN"


def _extract_transcript(response: Any) -> str:
    """Extract transcript text from a Hugging Face ASR response."""
    if isinstance(response, str):
        return response

    if isinstance(response, dict):
        text = response.get("text")
        return str(text) if text is not None else ""

    text = getattr(response, "text", None)
    return str(text) if text is not None else str(response)


def transcribe_audio(file_path: str) -> str:
    """Transcribe an audio file with Hugging Face Inference API."""
    audio = Path(file_path).read_bytes()
    client = InferenceClient(token=os.environ.get(HF_TOKEN_ENV_VAR))
    response = client.automatic_speech_recognition(
        audio,
        model=MODEL_NAME,
    )

    return _extract_transcript(response)
