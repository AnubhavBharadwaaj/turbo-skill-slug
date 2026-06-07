"""Tests for session extraction utilities."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock, patch

from extract import EXPECTED_KEYS, MODEL_NAME, SYSTEM_PROMPT, extract_session


def _sample_payload() -> dict[str, Any]:
    """Return a complete sample extraction payload."""
    return {
        "duration_minutes": 12,
        "themes": ["scaffolding", "audio"],
        "approaches_tried": [{"approach": "build a Gradio app", "outcome": "worked"}],
        "dead_ends": [{"position": 0.4, "what_happened": "pytest was missing"}],
        "breakthroughs": [{"position": 0.7, "what_worked": "mocked the client"}],
        "gotchas": ["network access needed approval"],
        "sentiment_arc": {"start": "curious", "end": "steady"},
        "skill_md": "# Skill\n\nUse the transcript.",
        "slug_voice": [
            "You waited through the install.",
            "The button found its job.",
            "The mock kept things tidy.",
            "The transcript became a map.",
            "The Space now has a trail.",
        ],
    }


def test_extract_session_returns_expected_keys() -> None:
    """The extractor parses chat completion JSON into the expected dict shape."""
    payload = _sample_payload()
    response = {
        "choices": [
            {
                "message": {
                    "content": f"```json\n{json.dumps(payload)}\n```",
                }
            }
        ]
    }

    with patch("extract.InferenceClient") as client_class:
        client = MagicMock()
        client.chat.completions.create.return_value = response
        client_class.return_value = client

        extraction = extract_session("session transcript")

    assert EXPECTED_KEYS.issubset(extraction.keys())
    client.chat.completions.create.assert_called_once_with(
        model=MODEL_NAME,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": "session transcript"},
        ],
        response_format={"type": "json_object"},
    )
