"""Session extraction utilities for TurboSkillSlug."""

from __future__ import annotations

import json
import os
import re
from typing import Any

from huggingface_hub import InferenceClient


MODEL_NAME = "Qwen/Qwen2.5-7B-Instruct"
HF_TOKEN_ENV_VAR = "HF_TOKEN"
EXPECTED_KEYS = {
    "duration_minutes",
    "themes",
    "approaches_tried",
    "dead_ends",
    "breakthroughs",
    "gotchas",
    "sentiment_arc",
    "skill_md",
    "slug_voice",
}
SYSTEM_PROMPT = (
    "You are TurboSkillSlug, a slow earnest companion who watched the build "
    "session. Return only a JSON object with these fields: duration_minutes "
    "(integer), themes (list of short strings), approaches_tried (list of "
    "objects with approach and outcome), dead_ends (list of objects with "
    "position as a float between 0 and 1 and what_happened), breakthroughs "
    "(list of objects with position and what_worked), gotchas (list of "
    "strings), sentiment_arc (object with start and end, each one word), "
    "skill_md (a clean SKILL.md in markdown), and slug_voice (exactly 5 short "
    "utterances in the slug's gentle voice, each grounded in the transcript, "
    "never generic)."
)


def _strip_code_fences(content: str) -> str:
    """Remove Markdown code fences from a model response before JSON parsing."""
    stripped = content.strip()
    fenced_match = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", stripped, re.DOTALL)
    return fenced_match.group(1).strip() if fenced_match else stripped


def _message_content(response: Any) -> str:
    """Extract assistant message content from a chat completion response."""
    if isinstance(response, dict):
        choices = response.get("choices", [])
        if choices:
            message = choices[0].get("message", {})
            return str(message.get("content", ""))

    choices = getattr(response, "choices", [])
    if choices:
        message = getattr(choices[0], "message", None)
        content = getattr(message, "content", None)
        if content is not None:
            return str(content)

    return str(response)


def _parse_json_object(content: str) -> dict[str, Any]:
    """Parse a JSON object from model content, tolerating code fences."""
    parsed = json.loads(_strip_code_fences(content))
    if not isinstance(parsed, dict):
        raise ValueError("Expected the model response to be a JSON object.")

    return parsed


def extract_session(transcript: str) -> dict[str, Any]:
    """Extract a structured TurboSkillSlug session recap from a transcript."""
    client = InferenceClient(provider="hf-inference", token=os.environ.get(HF_TOKEN_ENV_VAR))
    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": transcript},
        ],
        response_format={"type": "json_object"},
    )
    payload = _parse_json_object(_message_content(response))

    missing_keys = EXPECTED_KEYS - payload.keys()
    if missing_keys:
        missing = ", ".join(sorted(missing_keys))
        raise ValueError(f"Model response missing expected keys: {missing}")

    return payload
