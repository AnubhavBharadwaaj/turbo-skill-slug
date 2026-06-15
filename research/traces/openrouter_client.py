"""
OpenRouter client for the skill-uplift eval.

Reads the API key from the OPENROUTER_API_KEY environment variable. NEVER hardcode
the key; NEVER commit it. Set it in your shell:  export OPENROUTER_API_KEY=sk-or-...

Provides two factory helpers that return `complete(prompt) -> str` callables bound
to a specific model, so the eval's answerer and grader can be DIFFERENT models
(important: the grader must not be the same model that answered, to limit bias).
"""

from __future__ import annotations

import os
import time

import httpx

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
_KEY_ENV = "OPENROUTER_API_KEY"


def _key() -> str:
    k = os.environ.get(_KEY_ENV)
    if not k:
        raise RuntimeError(
            f"{_KEY_ENV} is not set. Run:  export {_KEY_ENV}=sk-or-...  "
            "(never paste the key into code or chat)."
        )
    return k


def make_completer(model: str, *, system: str | None = None,
                   temperature: float = 0.2, max_tokens: int = 900,
                   timeout: float = 90.0, retries: int = 2):
    """Return a complete(prompt)->str bound to `model` on OpenRouter."""
    def complete(prompt: str) -> str:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        body = {"model": model, "messages": messages,
                "temperature": temperature, "max_tokens": max_tokens}
        headers = {
            "Authorization": f"Bearer {_key()}",
            "Content-Type": "application/json",
            # OpenRouter likes these for attribution; harmless if omitted.
            "HTTP-Referer": "https://huggingface.co/spaces/build-small-hackathon/TurboSkillSlug",
            "X-Title": "TurboSkillSlug skill-uplift eval",
        }
        last_err = None
        for attempt in range(retries + 1):
            try:
                r = httpx.post(OPENROUTER_URL, json=body, headers=headers, timeout=timeout)
                r.raise_for_status()
                data = r.json()
                return data["choices"][0]["message"]["content"]
            except Exception as e:
                last_err = e
                time.sleep(1.5 * (attempt + 1))
        raise RuntimeError(f"OpenRouter call to {model} failed after retries: {last_err}")
    return complete


# Frontier model ids drift over time. These defaults reflect the OpenRouter
# catalog as of June 2026; OVERRIDE via env if the catalog has moved. Answerer and
# grader are intentionally DIFFERENT vendors to reduce self-grading bias.
DEFAULT_ANSWERER_MODEL = os.environ.get("EVAL_ANSWERER_MODEL", "anthropic/claude-opus-4.6")
DEFAULT_GRADER_MODEL   = os.environ.get("EVAL_GRADER_MODEL",   "openai/gpt-5.1")


def list_models() -> list[str]:
    """Fetch the live OpenRouter model catalog (ids only). Use this to verify a
    model id is currently valid before running, so a renamed model fails loud,
    not mid-eval."""
    headers = {"Authorization": f"Bearer {_key()}"}
    r = httpx.get("https://openrouter.ai/api/v1/models", headers=headers, timeout=30)
    r.raise_for_status()
    return [m["id"] for m in r.json().get("data", [])]


def verify_models(*model_ids: str) -> dict:
    """Return {model_id: is_available} by checking against the live catalog.
    Call this before run_eval so a stale id surfaces immediately."""
    try:
        catalog = set(list_models())
    except Exception as e:
        return {mid: f"could not verify ({e})" for mid in model_ids}
    return {mid: (mid in catalog) for mid in model_ids}
