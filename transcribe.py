"""Audio transcription utilities for TurboSkillSlug."""

from __future__ import annotations

import io
import os
from typing import Any

from huggingface_hub import InferenceClient


MODEL_NAME = "openai/whisper-large-v3-turbo"
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
    client = InferenceClient(provider="hf-inference", token=os.environ.get(HF_TOKEN_ENV_VAR))
    with open(file_path, "rb") as audio_file:
        audio_data = audio_file.read()
    buf = io.BytesIO(audio_data)
    buf.content_type = "audio/wav"

    response = client.automatic_speech_recognition(
        buf,
        model=MODEL_NAME,
    )

    return _extract_transcript(response)
