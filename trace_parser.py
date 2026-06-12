"""
Parse agent session logs (Claude Code + Codex CLI JSONL) into a narrative
transcript the TurboSkillSlug pipeline can read like spoken testimony.

The slug does not need full telemetry. It needs the STORY: what was asked,
what was tried, what errored (dead ends), what finally worked (breakthrough).
We render the trace as a first-person narrative so the extraction LoRA and
voice LoRA treat it exactly like an audio transcript.

Supports:
  - Claude Code: ~/.claude/projects/<encoded>/<uuid>.jsonl
    Each line: {"type": "user"|"assistant"|"tool_use"|"tool_result"|"system",
                "message": {"content": str | [content blocks]}, ...}
  - Codex CLI: ~/.codex/sessions/YYYY/MM/DD/rollout-*.jsonl
    Each line is a typed event (message, tool call, command output, patch).
    Multiple schema versions handled defensively.

Usage:
  from trace_parser import parse_trace_to_transcript
  text = parse_trace_to_transcript(jsonl_string)   # feed to existing pipeline
"""

from __future__ import annotations

import json
from typing import Any


# Tool-result text that signals an error / dead end
ERROR_MARKERS = (
    "error", "failed", "exception", "traceback", "not found", "cannot",
    "denied", "refused", "timeout", "timed out", "exit code 1", "exit status 1",
    "no such file", "undefined", "is not defined", "syntaxerror", "typeerror",
    "modulenotfound", "command not found", "fatal", "panic",
)

# Tool-result / message text that signals success / breakthrough
SUCCESS_MARKERS = (
    "passed", "success", "all tests pass", "tests passed", "ok", "done",
    "fixed", "resolved", "works now", "working", "0 failed", "exit code 0",
    "build succeeded", "compiled", "no errors",
)


def _content_to_text(content: Any) -> str:
    """Flatten Claude/Codex message content (str or list of blocks) to text."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict):
                # Claude content blocks: {"type": "text", "text": ...}
                # tool_use: {"type":"tool_use","name":...,"input":...}
                # tool_result: {"type":"tool_result","content":...}
                if block.get("type") == "text" and "text" in block:
                    parts.append(str(block["text"]))
                elif block.get("type") == "tool_use":
                    name = block.get("name", "a tool")
                    cmd = ""
                    inp = block.get("input", {})
                    if isinstance(inp, dict):
                        cmd = inp.get("command") or inp.get("file_path") or inp.get("path") or ""
                    parts.append(f"[ran {name} {cmd}]".strip())
                elif block.get("type") == "tool_result":
                    inner = block.get("content", "")
                    parts.append(_content_to_text(inner))
                elif "text" in block:
                    parts.append(str(block["text"]))
            elif isinstance(block, str):
                parts.append(block)
        return " ".join(p for p in parts if p)
    if isinstance(content, dict):
        return _content_to_text(content.get("content", "")) or str(content.get("text", ""))
    return ""


def _classify(text: str) -> str:
    """Tag a tool result as error, success, or neutral."""
    low = text.lower()
    if any(m in low for m in ERROR_MARKERS):
        return "error"
    if any(m in low for m in SUCCESS_MARKERS):
        return "success"
    return "neutral"


def _iter_events(jsonl_string: str):
    """Yield parsed JSON objects from a JSONL string, skipping bad lines."""
    for line in jsonl_string.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            yield json.loads(line)
        except json.JSONDecodeError:
            continue


def _blocks_contain(content: Any, block_type: str) -> bool:
    """True if content is a list containing a block of the given type."""
    if isinstance(content, list):
        return any(
            isinstance(b, dict) and b.get("type") == block_type for b in content
        )
    return False


def _extract_role_and_text(event: dict) -> tuple[str, str]:
    """Return (role, text) from one event across Claude + Codex schemas."""
    etype = event.get("type", "")

    # Claude Code shape: message under "message"
    msg = event.get("message")
    if isinstance(msg, dict):
        content = msg.get("content", "")
        text = _content_to_text(content)
        # Claude wraps tool results in a role="user" message — detect by block
        # type, not role, so they are classified as results not user turns.
        if _blocks_contain(content, "tool_result"):
            return "tool_result", text
        if _blocks_contain(content, "tool_use"):
            return "tool_use", text
        return msg.get("role", etype), text

    # Codex shapes: several versions
    # newer: {"type":"message","role":...,"content":[...]}
    if etype == "message" and "content" in event:
        return event.get("role", "assistant"), _content_to_text(event["content"])
    # tool/command events
    if etype in ("function_call", "tool_call", "local_shell_call", "exec"):
        name = event.get("name") or event.get("tool") or "command"
        args = event.get("arguments") or event.get("input") or event.get("command") or ""
        if isinstance(args, (dict, list)):
            args = _content_to_text(args)
        return "tool_use", f"[ran {name} {args}]".strip()
    if etype in ("function_call_output", "tool_result", "exec_output", "command_output"):
        out = event.get("output") or event.get("content") or event.get("result") or ""
        return "tool_result", _content_to_text(out) if not isinstance(out, str) else out
    # generic fallback
    if "content" in event:
        return event.get("role", etype or "system"), _content_to_text(event["content"])
    if "text" in event:
        return etype or "system", str(event["text"])

    return "", ""


def parse_trace_to_transcript(jsonl_string: str, max_chars: int = 6000) -> str:
    """
    Convert an agent session JSONL trace into a first-person narrative the
    slug can witness. Errors become dead ends, successes become breakthroughs.
    """
    lines: list[str] = []
    n_errors = 0
    n_success = 0
    n_tools = 0
    first_ask = None

    for event in _iter_events(jsonl_string):
        role, text = _extract_role_and_text(event)
        text = (text or "").strip()
        if not text or len(text) < 3:
            continue
        # Trim very long tool dumps to their first informative chunk
        if len(text) > 400:
            text = text[:400].rsplit(" ", 1)[0] + " ..."

        if role in ("user",) and first_ask is None:
            first_ask = text
            lines.append(f"I started by asking the agent: {text}")
        elif role in ("user",):
            lines.append(f"Then I told it: {text}")
        elif role in ("assistant",):
            lines.append(f"The agent said: {text}")
        elif role in ("tool_use",):
            n_tools += 1
            lines.append(text)  # already "[ran X ...]"
        elif role in ("tool_result",):
            kind = _classify(text)
            if kind == "error":
                n_errors += 1
                lines.append(f"That failed: {text}")
            elif kind == "success":
                n_success += 1
                lines.append(f"That worked: {text}")
            else:
                lines.append(f"It returned: {text}")
        # skip system events

    if not lines:
        return ""

    # Frame the narrative so the extraction model reads dead ends / breakthroughs
    header = (
        "This is a recording of a coding session I worked through with an AI "
        "agent. Here is what happened, start to finish.\n\n"
    )
    body = " ".join(lines)
    footer = (
        f"\n\nOver the session there were {n_errors} failures, {n_success} "
        f"successes, and {n_tools} tool runs. "
    )
    if n_errors > n_success:
        footer += "It was a grind with a lot of dead ends."
    elif n_success > 0 and n_errors == 0:
        footer += "It went smoothly start to finish."
    elif n_success > 0:
        footer += "After the failures, it finally came together."

    transcript = header + body + footer
    if len(transcript) > max_chars:
        # Keep the head (the ask + early attempts) and the tail (the resolution)
        head = transcript[: max_chars // 2]
        tail = transcript[-max_chars // 2 :]
        transcript = head + " ... " + tail
    return transcript


def detect_trace_format(jsonl_string: str) -> str:
    """Best-effort label of the trace source for display. 'claude', 'codex', or 'unknown'."""
    for event in _iter_events(jsonl_string):
        if isinstance(event.get("message"), dict):
            return "claude"
        if event.get("type") in ("function_call", "local_shell_call", "exec",
                                  "function_call_output", "exec_output"):
            return "codex"
    return "unknown"
