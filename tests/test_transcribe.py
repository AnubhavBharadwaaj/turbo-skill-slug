"""Tests for audio transcription utilities."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from transcribe import MODEL_NAME, transcribe_audio


def test_transcribe_audio_returns_string(tmp_path: Path) -> None:
    """The transcriber returns transcript text from the InferenceClient."""
    audio_path = tmp_path / "audio.wav"
    audio_path.write_bytes(b"fake audio")

    with patch("transcribe.InferenceClient") as client_class:
        client = MagicMock()
        client.automatic_speech_recognition.return_value = {"text": "hello slug"}
        client_class.return_value = client

        transcript = transcribe_audio(str(audio_path))

    assert transcript == "hello slug"
    assert isinstance(transcript, str)
    client.automatic_speech_recognition.assert_called_once_with(
        b"fake audio",
        model=MODEL_NAME,
    )
