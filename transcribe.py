"""Audio transcription via direct API call to HF Inference."""

import mimetypes
import os

import httpx


HF_TOKEN = os.environ.get("HF_TOKEN")
API_URL = "https://router.huggingface.co/hf-inference/models/openai/whisper-large-v3-turbo"


def transcribe_audio(file_path: str) -> str:
    """Transcribe audio file using Whisper via HF Inference API."""
    content_type = mimetypes.guess_type(file_path)[0] or "audio/wav"
    headers = {
        "Authorization": f"Bearer {HF_TOKEN}",
        "Content-Type": content_type,
    }
    with open(file_path, "rb") as f:
        data = f.read()
    response = httpx.post(API_URL, headers=headers, content=data, timeout=120.0)
    response.raise_for_status()
    result = response.json()
    return result.get("text", str(result))
