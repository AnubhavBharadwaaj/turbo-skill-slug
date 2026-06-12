"""Session extraction utilities for TurboSkillSlug.

Primary path: fine-tuned 1.5B extraction LoRA + voice LoRA served on Modal
(one T4, two adapters). Total active inference for extraction + voice is ~1.5B,
and with Whisper (809M) the full pipeline is ~2.6B.

The Qwen-7B is retained ONLY as a labeled fallback when the Modal endpoint is
unavailable (cold-start timeout, network error). The primary path does not use it.
"""

from __future__ import annotations

import json
import os
import re
import urllib.request
from typing import Any

from huggingface_hub import InferenceClient


# Modal dual-adapter endpoint (extraction LoRA + voice LoRA on one T4)
DUAL_URL = os.environ.get(
    "MODAL_DUAL_URL",
    "https://anubhavbharadwaaj--slug-dual-serve-dualserver-api.modal.run",
)

# Fallback only — not used in the primary path
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
SENTIMENT_START_DEFAULT = "focused"
SENTIMENT_END_DEFAULT = "resolved"
REQUIRED_SKILL_MD_SECTIONS = (
    "Problem",
    "Context",
    "Approaches Tried",
    "Breakthrough",
    "Final Solution",
    "Gotchas",
    "Tags",
)

# Used only by the 7B fallback path
SYSTEM_PROMPT = """\
You are TurboSkillSlug, a slow earnest companion who watched this build \
session from beginning to end. You speak as a witness who was present. \
You noticed specific moments: when the speaker repeated something, when \
they went quiet, when they changed direction, when something finally worked.

Return ONLY a JSON object (no preamble, no code fences) with these fields:

duration_minutes: integer, your best estimate from the transcript.

themes: list of 2 to 4 short lowercase tag strings.

approaches_tried: list of objects, each with "approach" (short phrase) and \
"why_it_failed" (one sentence). Include every distinct approach mentioned.

dead_ends: list of objects, each with "position" (float 0 to 1 indicating \
where in the session it occurred) and "what_happened". Every failed approach \
IS a dead end. If the transcript describes 4 failures, produce 4 dead ends. \
If the session was smooth with no failures, produce an empty list.

breakthroughs: list of objects with "position" and "what_worked".

gotchas: list of short strings. Capture every pitfall or surprise mentioned.

sentiment_arc: object with "start" and "end", each exactly one word.
  start must be one of: confused, focused, frustrated, curious.
  end must be one of: resolved, joyful, exhausted, enlightened.
  Choose honestly:
  - "frustrated" = speaker sounds stuck, annoyed, says "ugh" or "why"
  - "curious" = speaker is exploring, interested, not stuck
  - "focused" = speaker is calm, methodical, working through steps
  - "confused" = speaker genuinely does not understand
  - "resolved" = a specific bug or problem was fixed
  - "joyful" = session was easy and pleasant, speaker sounds delighted
  - "exhausted" = session was long and draining, speaker sounds tired
  - "enlightened" = speaker gained deep understanding
  Do NOT default to "resolved." A quick easy session ends "joyful." \
A long draining session ends "exhausted."

skill_md: a markdown document with these sections in order: \
Problem, Context, Approaches Tried (with why each failed), Breakthrough, \
Final Solution, Gotchas, Tags.

slug_voice: exactly 5 short sentences. These are the most important part. \
Rules:
1. Each sentence must reference a SPECIFIC moment from THIS transcript. \
Quote or paraphrase something the speaker actually said or did.
2. Speak in second person ("you") as someone who watched.
3. Be concrete. Mention what was tried, what broke, what changed. \
Use details from the transcript: tool names, error messages, variable names.
4. Never summarize. Never give advice. Never state facts about the topic. \
Only describe what you witnessed the speaker do.
5. Keep each sentence under 20 words.
6. The tone is quiet, earnest, specific. Not excited. Not cute. Not wise. \
Just present.
7. DO NOT write generic observations that could apply to any session. \
Every sentence must be impossible to write without having heard THIS transcript.\
"""


def _strip_code_fences(content: str) -> str:
    """Remove Markdown code fences from a model response before JSON parsing."""
    stripped = content.strip()
    fenced_match = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", stripped, re.DOTALL)
    return fenced_match.group(1).strip() if fenced_match else stripped


def _extract_json_object(content: str) -> dict[str, Any] | None:
    """Robustly pull the first complete JSON object, tolerating trailing text."""
    text = _strip_code_fences(content)
    start = text.find("{")
    if start == -1:
        return None
    depth = 0
    in_str = False
    escape = False
    for i in range(start, len(text)):
        c = text[i]
        if escape:
            escape = False
            continue
        if c == "\\":
            escape = True
            continue
        if c == '"':
            in_str = not in_str
            continue
        if not in_str:
            if c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    candidate = re.sub(
                        r"[\x00-\x08\x0b\x0c\x0e-\x1f]", " ", text[start:i + 1]
                    )
                    try:
                        return json.loads(candidate)
                    except json.JSONDecodeError:
                        return None
    return None


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


def _validate_sentiment_arc(payload: dict[str, Any]) -> None:
    """Clamp sentiment values to allowed sets instead of crashing."""
    sentiment_arc = payload.get("sentiment_arc")
    if not isinstance(sentiment_arc, dict):
        payload["sentiment_arc"] = {
            "start": SENTIMENT_START_DEFAULT,
            "end": SENTIMENT_END_DEFAULT,
        }
        return

    start = str(sentiment_arc.get("start", "")).lower().strip()
    if start not in SENTIMENT_START_VALUES:
        mapping = {
            "anxious": "frustrated",
            "nervous": "confused",
            "excited": "curious",
            "determined": "focused",
            "lost": "confused",
            "stuck": "frustrated",
            "calm": "focused",
            "interested": "curious",
        }
        start = mapping.get(start, SENTIMENT_START_DEFAULT)
    sentiment_arc["start"] = start

    end = str(sentiment_arc.get("end", "")).lower().strip()
    if end not in SENTIMENT_END_VALUES:
        mapping = {
            "satisfied": "resolved",
            "happy": "joyful",
            "relieved": "resolved",
            "tired": "exhausted",
            "drained": "exhausted",
            "content": "resolved",
            "excited": "joyful",
            "understood": "enlightened",
        }
        end = mapping.get(end, SENTIMENT_END_DEFAULT)
    sentiment_arc["end"] = end


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
        skeleton = "\n\n".join(
            f"## {section}\n_(not captured)_" for section in missing_sections
        )
        payload["skill_md"] = f"{skill_md}\n\n{skeleton}"


def _validate_slug_voice(payload: dict[str, Any]) -> None:
    """Ensure slug_voice has 5 non-empty strings, padding if needed."""
    slug_voice = payload.get("slug_voice")
    if not isinstance(slug_voice, list):
        slug_voice = []

    slug_voice = [str(u).strip() for u in slug_voice if str(u).strip()]

    if len(slug_voice) > 5:
        slug_voice = slug_voice[:5]
    while len(slug_voice) < 5:
        slug_voice.append("The slug watched but could not find the words.")

    payload["slug_voice"] = slug_voice


def _fill_missing_keys(payload: dict[str, Any]) -> None:
    """Default any missing optional keys so the smaller model's output survives."""
    payload.setdefault("duration_minutes", 5)
    payload.setdefault("themes", [])
    payload.setdefault("approaches_tried", [])
    payload.setdefault("dead_ends", [])
    payload.setdefault("breakthroughs", [])
    payload.setdefault("gotchas", [])
    payload.setdefault("skill_md", "")
    payload.setdefault("slug_voice", [])
    payload.setdefault("sentiment_arc", {})


def _finalize(payload: dict[str, Any]) -> dict[str, Any]:
    """Run the full validator chain. Works for both Modal and fallback output."""
    _fill_missing_keys(payload)
    _validate_sentiment_arc(payload)
    _validate_skill_md(payload)
    _validate_slug_voice(payload)
    return payload


def _call_dual(transcript: str, mode: str, timeout: int = 120) -> dict[str, Any] | None:
    """Call the Modal dual-adapter endpoint. Returns parsed JSON or None on failure."""
    try:
        data = json.dumps({"transcript": transcript, "mode": mode}).encode()
        req = urllib.request.Request(
            DUAL_URL, data=data, headers={"Content-Type": "application/json"}
        )
        resp = urllib.request.urlopen(req, timeout=timeout)
        return json.loads(resp.read())
    except Exception as e:
        print(f"Modal dual endpoint ({mode}) failed: {e}")
        return None


def _extract_via_modal(transcript: str) -> dict[str, Any] | None:
    """Primary path: extraction LoRA for the JSON, voice LoRA for slug_voice."""
    extract_resp = _call_dual(transcript, "extract")
    if not extract_resp or "extraction_raw" not in extract_resp:
        return None

    payload = _extract_json_object(extract_resp["extraction_raw"])
    if not payload:
        return None

    # Override slug_voice with the dedicated voice adapter's output
    voice_resp = _call_dual(transcript, "voice")
    if voice_resp and isinstance(voice_resp.get("slug_voice"), list):
        payload["slug_voice"] = voice_resp["slug_voice"]

    return payload


def _extract_via_fallback(transcript: str) -> dict[str, Any]:
    """Fallback only: Qwen-7B via HF Inference. Used when Modal is unavailable."""
    print("Falling back to Qwen-7B via HF Inference (Modal endpoint unavailable)")
    client = InferenceClient(token=os.environ.get(HF_TOKEN_ENV_VAR))
    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": transcript},
        ],
        response_format={"type": "json_object"},
    )
    payload = _extract_json_object(_message_content(response))
    if payload is None:
        raise ValueError("Fallback model did not return parseable JSON.")
    return payload


def extract_session(transcript: str) -> dict[str, Any]:
    """Extract a structured TurboSkillSlug session recap from a transcript.

    Primary path uses the fine-tuned 1.5B extraction + voice LoRAs on Modal
    (~2.6B total pipeline with Whisper). Falls back to Qwen-7B only if the
    Modal endpoint is unavailable.
    """
    payload = _extract_via_modal(transcript)

    if payload is None:
        payload = _extract_via_fallback(transcript)

    return _finalize(payload)
