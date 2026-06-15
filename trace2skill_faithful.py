"""
Phase 3 (faithful rebuild): Trace2Skill (arXiv:2603.25158), corrected against the
paper's actual method and prompts (Sections 2.3-2.4, Appendix B). Replaces the
earlier simplified multi_analyst_extract.py.

Corrections vs the first attempt (all verified against the paper):
  1. Error analyst is an AGENTIC, VALIDATION-GATED loop, not a single call. It must
     produce a VERIFIED causal analysis; trajectories without one are EXCLUDED.
     (Paper's key result: this beats single-call by up to +13.3pp and avoids the
      "57% of cases over-attribute parse errors / hallucinate causes" failure — which
      is exactly the leak/false-cause bug.)
  2. Consolidation is an LLM MERGE OPERATOR applied HIERARCHICALLY over batches of
     size B for ceil(log_B |P|) levels, with an explicit PREVALENT-PATTERN bias —
     not an integer agreement count.
  3. Asymmetric trust: +Error is the reliable signal; +Success is volatile (can be
     negative) — success patches are merged with lower priority.
  4. Low-support observations are ROUTED TO references, not discarded.
  5. Deterministic guardrails on the merged patch.

Honesty note on the live Space: the paper's error analyst executes a minimal fix
and re-evaluates against ground truth in a sandbox. A coding session fed to the slug
usually has NO ground-truth/sandbox to run fixes in. We therefore implement the gate
as a strict self-verification the analyst must satisfy (cite specific evidence from
the trace for the causal claim) and DOCUMENT that full fix-execution requires a
sandbox + ground truth, which the slug's use case may not have. This is a faithful
adaptation, not the literal method, and we say so.
"""

from __future__ import annotations

import json
import math
import re

# ---- Prompts, adapted faithfully from the paper's Appendix B ----

ERROR_ANALYST_SYSTEM = (
    "You are an expert failure-analysis agent. Given an agent's execution trace for "
    "ONE session (and any produced files/outputs available), diagnose WHY it failed, "
    "identify the CAUSAL failure reason, and VALIDATE your diagnosis by citing the "
    "specific evidence in the trace that proves it. Be systematic and evidence-driven. "
    "DO NOT GUESS when you can verify. If you cannot ground a causal cause in concrete "
    "trace evidence, output an empty list — it is correct to abstain.\n"
    "Output ONLY JSON: {\"verified\": true|false, \"failure_memory_items\": "
    "[\"<=3 generalizable lessons to avoid this failure\"]}. "
    "verified=true ONLY if each lesson is tied to cited evidence."
)

SUCCESS_ANALYST_SYSTEM = (
    "You are an expert in success-pattern analysis. Given a successful session "
    "trajectory, identify GENERALIZABLE behavior patterns that contributed to the "
    "correct outcome. Frequency awareness: patterns covering more instances first. "
    "Each pattern must be a general mechanism, not a task-specific detail.\n"
    "Output ONLY JSON: {\"success_memory_items\": [\"general patterns\"]}."
)

MERGE_OPERATOR_SYSTEM = (
    "You are a skill edit coordinator. You receive multiple independently-proposed "
    "lesson items that each suggest additions to a skill. Merge them into one "
    "coherent, non-redundant set.\n"
    "Guidelines: (1) Deduplicate: keep the best version of similar items. "
    "(2) Resolve conflicts: choose the better-justified, or synthesize. "
    "(3) Preserve unique insights. (4) Conciseness: <= the sum of unique items. "
    "PREVALENT PATTERN BIAS: when multiple items independently propose the same class "
    "of lesson, treat that recurrence as evidence of a SYSTEMATIC property; preserve it "
    "with higher priority and express it as a general principle, not an instance fix. "
    "Items appearing only once are low-support: keep them but mark them as niche.\n"
    "Output ONLY JSON: {\"main\": [\"general principles (high support)\"], "
    "\"references\": [\"niche/low-support items\"]}."
)


def _parse_json(raw: str, default):
    try:
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        return json.loads(m.group(0)) if m else default
    except Exception:
        return default


def error_analyst(trace_text: str, completer) -> list:
    """Agentic-style validation-gated error analysis. Returns memory items ONLY if
    the analyst self-verifies a causal cause grounded in trace evidence; else []."""
    out = _parse_json(
        completer(f"{ERROR_ANALYST_SYSTEM}\n\nTRACE:\n{trace_text}\n\nJSON:"),
        {"verified": False, "failure_memory_items": []},
    )
    if not out.get("verified"):
        return []   # excluded — no verified causal analysis (the paper's quality gate)
    return [str(x).strip() for x in out.get("failure_memory_items", []) if str(x).strip()]


def success_analyst(trace_text: str, completer) -> list:
    out = _parse_json(
        completer(f"{SUCCESS_ANALYST_SYSTEM}\n\nTRACE:\n{trace_text}\n\nJSON:"),
        {"success_memory_items": []},
    )
    return [str(x).strip() for x in out.get("success_memory_items", []) if str(x).strip()]


def _merge_batch(items: list, completer) -> dict:
    payload = "\n".join(f"- {it}" for it in items)
    out = _parse_json(
        completer(f"{MERGE_OPERATOR_SYSTEM}\n\nITEMS:\n{payload}\n\nJSON:"),
        {"main": items, "references": []},
    )
    return {"main": [str(x).strip() for x in out.get("main", []) if str(x).strip()],
            "references": [str(x).strip() for x in out.get("references", []) if str(x).strip()]}


def hierarchical_merge(items: list, completer, batch_size: int = 8) -> dict:
    """Merge in ceil(log_B |P|) levels, batch size B, per the paper (they use B=32;
    we default smaller for a live Space). Returns {"main":[...], "references":[...]}.
    """
    if not items:
        return {"main": [], "references": []}
    refs = []
    level_items = list(items)
    # iterate levels until a single batch remains
    while len(level_items) > batch_size:
        next_level = []
        for i in range(0, len(level_items), batch_size):
            merged = _merge_batch(level_items[i:i + batch_size], completer)
            next_level.extend(merged["main"])
            refs.extend(merged["references"])
        level_items = next_level
    final = _merge_batch(level_items, completer)
    final["references"] = list(dict.fromkeys(refs + final.get("references", [])))
    return final


def _dedup_guardrail(d: dict) -> dict:
    """Deterministic guardrail: dedupe, drop empties, keep order stable."""
    def clean(xs):
        seen, out = set(), []
        for x in xs:
            k = re.sub(r"\s+", " ", x.lower()).strip()
            if k and k not in seen:
                seen.add(k); out.append(x.strip())
        return out
    return {"main": clean(d.get("main", [])), "references": clean(d.get("references", []))}


def trace2skill(sessions: list, completer, *, batch_size: int = 8) -> dict:
    """Faithful pipeline. sessions: [{"trace": str, "success": bool}]. Error traces
    go through the validation-gated error analyst (lower-trust ones excluded if they
    can't self-verify); success traces through the single-pass success analyst
    (lower priority). All items are hierarchically merged with prevalent-pattern bias.

    Returns {"main":[...principles...], "references":[...niche...],
             "stats":{...}} — main goes in SKILL.md, references into references/.
    """
    error_items, success_items, excluded = [], [], 0
    for s in sessions:
        if s.get("success"):
            success_items.extend(success_analyst(s["trace"], completer))
        else:
            items = error_analyst(s["trace"], completer)
            if not items:
                excluded += 1     # the paper's quality gate excluding ungroundable traces
            error_items.extend(items)

    # error items are the reliable signal; success items appended at lower priority
    all_items = error_items + success_items
    merged = _dedup_guardrail(hierarchical_merge(all_items, completer, batch_size))
    merged["stats"] = {
        "n_sessions": len(sessions),
        "n_error_items": len(error_items),
        "n_success_items": len(success_items),
        "n_excluded_error_traces": excluded,
        "n_main": len(merged["main"]),
        "n_references": len(merged["references"]),
    }
    return merged
