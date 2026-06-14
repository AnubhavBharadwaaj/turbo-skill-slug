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
"why_it_failed" (a full sentence giving the REAL reason it failed, drawn from \
THIS transcript, not a vague label). State the actual mechanism of failure the \
session encountered. Include every distinct approach mentioned.

dead_ends: list of objects, each with "position" (float 0 to 1 indicating \
where in the session it occurred) and "what_happened". Every failed approach \
IS a dead end. If the transcript describes 4 failures, produce 4 dead ends. \
If the session was smooth with no failures, produce an empty list.

breakthroughs: list of objects with "position" and "what_worked".

gotchas: list of strings. Each gotcha is a NON-OBVIOUS trap from THIS specific \
problem that a capable engineer would still get wrong without being warned. \
A good gotcha is useful even to an expert: it names the symptom, the cause, and \
what to do, in one self-contained sentence drawn ONLY from this transcript. \
Do not write vague labels like "state space too large" or "ordering unclear" — \
state WHY it is too large and WHAT to do about it, using the specifics this \
session actually encountered. If a pitfall cannot be stated with its cause and \
fix from what was said, leave it out. Prefer 2 deep, specific gotchas over 6 \
shallow labels. Never invent details that were not in the transcript.

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


def _gotcha_completer(prompt: str) -> str:
    """One-shot text completion used only to enrich terse gotchas. Uses the same
    HF Inference 7B that backs the fallback. Best-effort: any failure leaves the
    gotchas as-is."""
    client = InferenceClient(token=os.environ.get(HF_TOKEN_ENV_VAR))
    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {"role": "system", "content": "You sharpen coding gotchas into precise, "
             "transferable advice. Return only what is asked."},
            {"role": "user", "content": prompt},
        ],
    )
    return _message_content(response)


def _validate_skill_md(payload: dict[str, Any]) -> None:
    """Build the SKILL.md from the structured extraction rather than trusting the
    model's raw prose.

    The model is good at extracting the structure (approaches, why each failed,
    gotchas, what worked). Assembling that into a genuinely useful, transferable
    skill — gotchas-first, with explicit 'what not to do and why' — is mechanical
    and is done deterministically so every skill has the shape that gives an LLM
    real uplift over solving from scratch. See skill_builder for the rationale.

    If terse gotchas slipped through, an optional one-shot enrichment pass
    expands them into symptom/cause/fix form. It is best-effort and never blocks.
    """
    try:
        from skill_builder import build_skill_md, enrich_gotchas
        # Optional depth pass: only fires if terse gotchas are present, and only
        # if the enrichment call succeeds. Controlled by env so it can be turned
        # off (e.g. to keep latency down) without code changes.
        if os.environ.get("SLUG_ENRICH_GOTCHAS", "1") == "1":
            try:
                payload.update(enrich_gotchas(payload, complete=_gotcha_completer))
            except Exception:
                pass
        payload["skill_md"] = build_skill_md(payload)
        return
    except Exception:
        # If the builder fails for any reason, fall back to patching the model's
        # raw skill_md so we never block the response.
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


def _call_dual(transcript: str, mode: str, timeout: int = 180) -> dict[str, Any] | None:
    """Call the Modal dual-adapter endpoint. Returns parsed JSON or None on failure."""
    try:
        data = json.dumps({"transcript": transcript, "mode": mode}).encode()
        req = urllib.request.Request(
            DUAL_URL, data=data, headers={"Content-Type": "application/json"}
        )
        resp = urllib.request.urlopen(req, timeout=timeout)
        return json.loads(resp.read())
    except Exception as e:
        # Surfaced by _vlog's VOICE_DOWN/EXTRACT_DOWN cases; this line gives the
        # underlying reason (timeout / connection refused = container stopped /
        # HTTP error). If you see this for 'voice', restart slug-dual-serve.
        print(f"[DUAL] {mode} call failed: {type(e).__name__}: {e}")
        return None


_COUNT_SENTENCE_RE = re.compile(
    r"[^.]*\b(?:over the session|there were|failures?|successes?|tool runs?|"
    r"dead ends?|breakthroughs?)\b[^.]*\d[^.]*\.",
    re.IGNORECASE,
)

# Number words the voice model tends to invent
_NUMBER_WORDS = (
    "one", "two", "three", "four", "five",
    "six", "seven", "eight", "nine", "ten",
)

# A voice line is "reciting a tally" if it pairs a count (digit or number word)
# with an event noun. The slug witnesses moments; tallies belong on the receipt
# and shell, not in its voice. Reciting counts is where it invents false ones.
_TALLY_RE = re.compile(
    r"\b(?:\d{1,2}|" + "|".join(_NUMBER_WORDS) + r")\b"
    r"[^.]{0,40}?\b(?:failure|success|wall|walls|tool|tools|attempt|attempts|"
    r"try|tries|step|steps|dead end|dead ends|breakthrough|breakthroughs|"
    r"time|times|mistake|mistakes)\b",
    re.IGNORECASE,
)


def _strip_count_summary(transcript: str) -> str:
    """Remove count-summary sentences so the voice model describes moments,
    not tallies. The footer like 'there were 2 failures, 1 successes...' is
    exactly what makes the slug invent contradictory numbers."""
    return _COUNT_SENTENCE_RE.sub("", transcript).strip()


def _voice_line_recites_tally(line: str) -> bool:
    """True if a line recites an event count (e.g. 'three walls', '2 failures').

    The slug must never lie about what it witnessed, and the safest way to keep
    it honest is to forbid it from reciting tallies at all. Counts live on the
    receipt and in the shell; the voice describes specific moments. A line that
    pairs a number with an event noun is dropped regardless of whether the
    number happens to be right, because reciting counts is not the slug's job.
    """
    return bool(_TALLY_RE.search(line))


def _guard_slug_voice(lines: list[str]) -> list[str]:
    """Drop voice lines that recite event tallies (the source of false counts)."""
    return [ln for ln in lines if not _voice_line_recites_tally(ln)]


def _voice_from_extraction(payload: dict[str, Any]) -> list[str]:
    """Deterministic slug-voice lines built from the structured extraction.

    Used only as a SAFETY NET when the voice adapter is unavailable and the
    extraction payload carries no usable slug_voice. It keeps the recap from
    degrading to five identical placeholders. These lines describe witnessed
    moments (never tallies), so they pass the same guard as the model voice.
    """
    lines: list[str] = []
    themes = payload.get("themes") or []
    approaches = payload.get("approaches_tried") or []
    dead_ends = payload.get("dead_ends") or []
    breakthroughs = payload.get("breakthroughs") or []
    arc = payload.get("sentiment_arc") or {}

    if themes:
        lines.append(f"You sat with a {', '.join(themes[:2])} problem, turning it over.")
    if approaches:
        a = approaches[0]
        ap = a.get("approach") if isinstance(a, dict) else None
        if ap:
            lines.append(f"You reached for {ap}, and watched where it led.")
    if dead_ends:
        d = dead_ends[0]
        what = d.get("what_happened") if isinstance(d, dict) else None
        if what:
            lines.append(f"It stalled when {str(what).rstrip('.').lower()}.")
        else:
            lines.append("You hit a wall and had to back out of it.")
    if breakthroughs:
        b = breakthroughs[-1]
        w = b.get("what_worked") if isinstance(b, dict) else None
        if w:
            lines.append(f"Then it gave way: {str(w).rstrip('.').lower()}.")
    start, end = arc.get("start"), arc.get("end")
    if start and end:
        lines.append(f"You went in {start} and came out {end}.")

    # keep only guarded, non-empty lines; this never invents counts
    lines = _guard_slug_voice([ln for ln in lines if ln and ln.strip()])
    return lines[:5]


def _vlog(case: str, detail: str = "") -> None:
    """Structured diagnostic for the slug-voice path. Every outcome is logged with
    a stable [VOICE] tag and an explicit CASE so the Space logs name exactly what
    happened — no guessing from a placeholder recap.

    Cases (search the Space logs for '[VOICE]'):
      EXTRACT_DOWN       extract endpoint returned nothing -> whole modal path fails
      VOICE_DOWN         voice endpoint call returned None (timeout/stopped/error)
      VOICE_EMPTY        voice endpoint replied but slug_voice was empty/not a list
      VOICE_ALL_TALLIES  voice lines were all dropped by the tally guard
      VOICE_OK           voice adapter lines used (N kept)
      NET_FROM_EXTRACTION deterministic fallback built from the extraction (N lines)
      NET_FAILED         even the deterministic fallback produced nothing -> padding
    """
    print(f"[VOICE] {case}" + (f" :: {detail}" if detail else ""))


def _extract_via_modal(transcript: str) -> dict[str, Any] | None:
    """Primary path: extraction LoRA for the JSON, voice LoRA for slug_voice."""
    extract_resp = _call_dual(transcript, "extract")
    if not extract_resp or "extraction_raw" not in extract_resp:
        _vlog("EXTRACT_DOWN", "extract endpoint returned no extraction_raw")
        return None

    payload = _extract_json_object(extract_resp["extraction_raw"])
    if not payload:
        _vlog("EXTRACT_DOWN", "extraction_raw did not parse to JSON")
        return None

    # Override slug_voice with the dedicated voice adapter's output.
    # Strip the count-summary footer first so the slug describes moments,
    # not tallies (the footer is what makes it invent contradictory numbers).
    voice_input = _strip_count_summary(transcript)
    voice_resp = _call_dual(voice_input, "voice")

    if voice_resp is None:
        # _call_dual already printed the underlying exception; tag the case.
        _vlog("VOICE_DOWN", "voice endpoint call returned None (see preceding error)")
    elif not isinstance(voice_resp.get("slug_voice"), list) or not voice_resp.get("slug_voice"):
        _vlog("VOICE_EMPTY", f"voice reply had no usable slug_voice list: keys={list(voice_resp.keys())}")
    else:
        raw_lines = voice_resp["slug_voice"]
        guarded = _guard_slug_voice(raw_lines)
        if guarded:
            payload["slug_voice"] = guarded
            dropped = len(raw_lines) - len(guarded)
            _vlog("VOICE_OK", f"{len(guarded)} lines kept"
                              + (f", {dropped} dropped as tallies" if dropped else ""))
        else:
            _vlog("VOICE_ALL_TALLIES", f"all {len(raw_lines)} voice lines were tallies, dropped")

    # SAFETY NET: if after all that slug_voice is empty/missing (voice adapter
    # was down, and the extract adapter emitted no usable voice), build voice
    # from the structured extraction so the recap is never five identical
    # "could not find the words" placeholders.
    existing = _guard_slug_voice(
        [str(u).strip() for u in (payload.get("slug_voice") or []) if str(u).strip()]
    )
    if not existing:
        derived = _voice_from_extraction(payload)
        if derived:
            payload["slug_voice"] = derived
            _vlog("NET_FROM_EXTRACTION", f"{len(derived)} deterministic lines built from extraction")
        else:
            _vlog("NET_FAILED", "extraction too sparse to derive voice -> recap will show placeholders")

    return payload


def _extract_via_fallback(transcript: str) -> dict[str, Any]:
    """Fallback only: Qwen-7B via HF Inference. Used when Modal is unavailable."""
    print("[FALLBACK] Modal primary path unavailable -> Qwen-7B via HF Inference")
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
