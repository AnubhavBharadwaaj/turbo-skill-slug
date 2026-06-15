"""
Phase 1 (part 2): RuleShaping-grounded negative-constraint phrasing for L3 rules.

Grounded in RuleShaping — "Do Agent Rules Shape or Distort?" (arXiv:2604.11088,
verified against the paper): rules improve +7–14pp; NEGATIVE constraints are the
ONLY individually beneficial rule type, POSITIVE directives actively HURT, and rules
work through CONTEXT PRIMING (random rules help nearly as much as curated). The
highest-benefit category is STATE-DEPENDENT process guardrails (do not X until Y),
63.8%. So L3 rules the slug emits are phrased as negative, preferably state-dependent,
guardrails. Individual rules can be harmful in isolation but are collectively helpful
(no degradation up to 50 rules), so emitting several is fine.

This module provides:
  - is_negative_constraint(text): heuristic check
  - to_negative_constraint(gotcha): deterministic reshaping of a gotcha into a
    guardrail-phrased rule WITHOUT inventing content (it only re-frames what's there).

We keep this deterministic and conservative: if we cannot confidently reshape, we
return the original prefixed minimally, rather than fabricate a cause.
"""

from __future__ import annotations

import re

_POSITIVE_OPENERS = (
    "always ", "make sure to ", "be sure to ", "remember to ", "you should ",
    "ensure that ", "ensure you ", "prefer ", "use ",
)
_NEGATIVE_MARKERS = (
    "avoid", "do not", "don't", "never", "without", "fails", "breaks",
    "silently", "instead of", "rather than", "watch out", "beware",
)


def is_negative_constraint(text: str) -> bool:
    t = text.lower().strip()
    return any(m in t for m in _NEGATIVE_MARKERS)


def _split_cause(gotcha: str) -> tuple[str, str | None]:
    """Try to separate the 'what' from the 'why' using common connectives."""
    for sep in (" because ", " since ", "; ", " — ", " - ", ", which ", ", as "):
        if sep in gotcha:
            head, tail = gotcha.split(sep, 1)
            return head.strip(), tail.strip().rstrip(".")
    return gotcha.strip(), None


def to_negative_constraint(gotcha: str) -> str:
    """Reshape a gotcha into a guardrail-phrased rule. Content-preserving: we never
    invent a cause that isn't present; we only re-frame the existing text."""
    g = gotcha.strip().rstrip(".")
    if not g:
        return g
    # already a guardrail? keep it (just normalize trailing period)
    if is_negative_constraint(g):
        return g + "."

    what, why = _split_cause(g)

    # strip a leading positive opener so we can recast it
    low = what.lower()
    for opener in _POSITIVE_OPENERS:
        if low.startswith(opener):
            what = what[len(opener):].strip()
            break

    # Build a guardrail. If we have a cause, use "Avoid …; otherwise/ because …".
    # If not, we frame as a caution without fabricating a reason.
    # Pick a guardrail frame that doesn't collide with the gotcha's own wording.
    wl = what.lower()
    already = any(k in wl for k in ("assume", "assumes", "always", "is guaranteed"))
    if why:
        if already:
            return f"Do not rely on the assumption that {what} — {why}."
        return f"Avoid assuming {what} holds by default — {why}."
    if already:
        return f"Do not rely on the assumption that {what}; verify it explicitly."
    return f"Watch out: {what} is not guaranteed; verify it rather than assuming it."


def reshape_rules(gotchas: list[str]) -> list[str]:
    """Map a list of gotchas to guardrail-phrased rules, de-duplicated, order-stable."""
    seen, out = set(), []
    for g in gotchas:
        r = to_negative_constraint(g)
        key = r.lower()
        if key not in seen:
            seen.add(key)
            out.append(r)
    return out


# ---- LLM-based reshaping (primary path; deterministic above is the fallback) ----
# The deterministic reshaper preserves content but reads awkwardly. When a model
# completer is available, we use it to phrase the guardrail naturally, constrained
# to NOT invent any cause not present in the gotcha.

_RESHAPE_SYSTEM = (
    "You rewrite a single engineering 'gotcha' into a guardrail-style rule. Rules: "
    "(1) Phrase as a NEGATIVE constraint (do not / never / avoid), never a positive "
    "directive (no 'always', 'use', 'prefer') — per RuleShaping (arXiv:2604.11088), "
    "negative constraints are the only individually beneficial rule type; positive "
    "directives actively hurt. "
    "(2) PREFER a STATE-DEPENDENT PROCESS guardrail when the gotcha supports one: "
    "'do not X until/unless/before Y' (the highest-benefit category, 63.8%), rather "
    "than a state-independent architectural 'don't'. "
    "(3) Do NOT invent any cause/mechanism/detail not present in the input. "
    "(4) One sentence, under 30 words. (5) Output ONLY the rewritten rule."
)


def to_negative_constraint_llm(gotcha: str, completer) -> str:
    """Reshape via a model completer (prompt)->str. Falls back to the deterministic
    reshaper on any failure or if the output drifts into a positive directive."""
    g = gotcha.strip().rstrip(".")
    if not g:
        return g
    try:
        out = completer(f"{_RESHAPE_SYSTEM}\n\nGOTCHA:\n{g}\n\nGUARDRAIL RULE:").strip()
        out = out.strip().strip('"').rstrip(".") + "."
        # guard: reject if it came back as a positive directive or empty
        if not out or not is_negative_constraint(out):
            return to_negative_constraint(g)
        # guard against fabrication: if the model added a 'because' the source lacked,
        # and the source had no cause, fall back (conservative).
        _, why = _split_cause(g)
        if why is None and (" because " in out.lower() or " since " in out.lower()):
            return to_negative_constraint(g)
        return out
    except Exception:
        return to_negative_constraint(g)


def reshape_rules_llm(gotchas: list, completer) -> list:
    seen, out = set(), []
    for g in gotchas:
        r = to_negative_constraint_llm(g, completer)
        k = r.lower()
        if k not in seen:
            seen.add(k); out.append(r)
    return out
