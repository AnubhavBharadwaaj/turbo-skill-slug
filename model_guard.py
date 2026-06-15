"""
Compliance guard: makes it impossible to call an over-32B model from the live app path.

Build Small REQ-01: every model the *app* depends on must be < 32B total params.
Frontier models (Opus, GPT-5.x, etc.) are fine in OFFLINE eval/research scripts, but
must NEVER be on the deployed app's request path.

Usage in app.py (or any module that runs inside the live Space):
    from model_guard import assert_small_model, APP_RUNTIME
    APP_RUNTIME.enable()                      # call once at app startup
    assert_small_model(model_name)            # call before any model invocation

In offline research scripts, simply do NOT enable APP_RUNTIME, and frontier calls pass.

The guard is allow-list based: only known sub-32B models are permitted in app runtime.
Anything not on the allow-list (or matching a frontier pattern) raises immediately.
"""

from __future__ import annotations

import os
import re

# Sub-32B models your APP is allowed to use at runtime. Extend as needed.
ALLOWED_APP_MODELS = {
    "whisper", "whisper-large", "whisper-809m",
    "qwen2.5-1.5b", "qwen2.5-1.5b-instruct",
    "qwen2.5-7b", "qwen2.5-7b-instruct",        # legit fallback + gotcha enrichment (7B < 32B)
    "slugvoice", "slugextract",                 # your LoRAs on the 1.5B base
}

# Patterns that are ALWAYS frontier / over-cap — blocked in app runtime.
_FRONTIER_PATTERNS = [
    r"opus", r"sonnet", r"gpt-5", r"gpt-4", r"o1", r"o3", r"o4",
    r"claude-3", r"claude-4", r"claude-opus", r"claude-sonnet",
    r"\b\d{2,}b\b",         # any "...70b", "...405b" style tag >= 2 digits of B
    r"gemini-1\.5-pro", r"gemini-2", r"deepseek-v", r"llama-3\.1-405b",
]


class _AppRuntime:
    """Flag indicating we're inside the live app (not an offline research script)."""
    def __init__(self):
        self._on = os.environ.get("APP_RUNTIME", "") == "1"

    def enable(self):
        self._on = True

    def disable(self):
        self._on = False

    @property
    def active(self) -> bool:
        return self._on


APP_RUNTIME = _AppRuntime()


def _looks_frontier(model_name: str) -> bool:
    m = model_name.lower()
    return any(re.search(p, m) for p in _FRONTIER_PATTERNS)


def assert_small_model(model_name: str) -> None:
    """Raise if a frontier/over-cap model is used while the app runtime is active.
    No-op in offline research mode (APP_RUNTIME not enabled)."""
    if not APP_RUNTIME.active:
        return  # offline eval/research — frontier calls are allowed here
    name = (model_name or "").strip().lower()
    base = name.split("/")[-1]   # strip provider prefix like 'anthropic/'
    allowed = any(base.startswith(a) or a in base for a in ALLOWED_APP_MODELS)
    if _looks_frontier(name) or not allowed:
        raise RuntimeError(
            f"REQ-01 GUARD: refusing to call '{model_name}' from the live app path. "
            f"The deployed app may only use sub-32B models {sorted(ALLOWED_APP_MODELS)}. "
            f"Frontier models are allowed only in offline eval/research scripts "
            f"(do not call APP_RUNTIME.enable() there)."
        )
