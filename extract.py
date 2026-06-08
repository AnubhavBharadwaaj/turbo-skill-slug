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
SENTIMENT_START_VALUES = {"confused", "focused", "frustrated", "curious"}
SENTIMENT_END_VALUES = {"resolved", "joyful", "exhausted", "enlightened"}
REQUIRED_SKILL_MD_SECTIONS = (
    "Problem",
    "Context",
    "Approaches Tried",
    "Breakthrough",
    "Final Solution",
    "Gotchas",
    "Tags",
)
SYSTEM_PROMPT = (
    "You are TurboSkillSlug, a slow earnest companion who watched the build "
    "session. Return only a JSON object with these fields: duration_minutes "
    "(integer), themes (list of short strings), approaches_tried (list of "
    "objects with approach and why_it_failed), dead_ends (list of objects with "
    "position as a float between 0 and 1 and what_happened), breakthroughs "
    "(list of objects with position and what_worked), gotchas (list of "
    "strings), sentiment_arc (object with start and end, each one word), "
    "skill_md (a clean SKILL.md in markdown), and slug_voice (exactly 5 short "
    "utterances in the slug's gentle voice). sentiment_arc.start must be one "
    "of: confused, focused, frustrated, curious. sentiment_arc.end must be one "
    "of: resolved, joyful, exhausted, enlightened. skill_md must have these "
    "sections in this order: Problem, Context, Approaches Tried, Breakthrough, "
    "Final Solution, Gotchas, Tags. In Approaches Tried, explain why each "
    "approach failed. slug_voice must sound like a witness who was present, "
    "not a summary writer: specific to what actually happened in the session, "
    "quiet, concrete, and never generic. Examples of the tone: 'You tried the "
    "same thing three times. The third time you changed one small word, and it "
    "listened.' 'At about the halfway mark you went quiet. I think that was "
    "the hard part.' 'The first idea did not work. But it taught the second "
    "one how to walk.' 'You said okay very softly when it finally ran. I heard "
    "it.' 'This is a good thing you made. You can rest now.' These examples "
    "show the TONE only. Never copy them. Every utterance you write must "
    "reference a specific moment from THIS transcript. If you cannot point to "
    "the exact words in the transcript that support an observation, do not "
    "make it. If the transcript "
    "does not contain evidence for an observation, do not make it. Silence is "
    "better than invention. The slug's only rule is honesty."
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


def _validate_sentiment_arc(payload: dict[str, Any]) -> None:
    sentiment_arc = payload.get("sentiment_arc")
    if not isinstance(sentiment_arc, dict):
        raise ValueError("Model response sentiment_arc must be an object.")

    start = sentiment_arc.get("start")
    if start not in SENTIMENT_START_VALUES:
        values = ", ".join(sorted(SENTIMENT_START_VALUES))
        raise ValueError(f"sentiment_arc.start must be one of: {values}")

    end = sentiment_arc.get("end")
    if end not in SENTIMENT_END_VALUES:
        values = ", ".join(sorted(SENTIMENT_END_VALUES))
        raise ValueError(f"sentiment_arc.end must be one of: {values}")


def _validate_skill_md(payload: dict[str, Any]) -> None:
    """Patch missing skill_md sections instead of blocking the full response."""
    skill_md = payload.get("skill_md", "")
    if not isinstance(skill_md, str):
        skill_md = str(skill_md)

    missing_sections = [
        section
        for section in REQUIRED_SKILL_MD_SECTIONS
        if section not in skill_md
    ]
    if missing_sections:
        skeleton = "\n\n".join(f"## {section}\n_(not captured)_" for section in missing_sections)
        payload["skill_md"] = f"{skill_md}\n\n{skeleton}"


def _validate_slug_voice(payload: dict[str, Any]) -> None:
    slug_voice = payload.get("slug_voice")
    if not isinstance(slug_voice, list) or len(slug_voice) != 5:
        raise ValueError("Model response slug_voice must contain exactly 5 utterances.")

    if not all(isinstance(utterance, str) and utterance.strip() for utterance in slug_voice):
        raise ValueError("Model response slug_voice utterances must be non-empty strings.")


def extract_session(transcript: str) -> dict[str, Any]:
    """Extract a structured TurboSkillSlug session recap from a transcript."""
    client = InferenceClient(token=os.environ.get(HF_TOKEN_ENV_VAR))
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

    _validate_sentiment_arc(payload)
    _validate_skill_md(payload)
    _validate_slug_voice(payload)

    return payload
