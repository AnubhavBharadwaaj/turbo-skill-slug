"""
Build a genuinely useful SKILL.md from a session extraction.

The judge's note: the skill file should give an LLM real uplift even over a
frontier model that is already capable without it. Research on what makes skills
work (Anthropic skill-creator, Perplexity, SkillsBench) converges on a few
principles, and this module encodes them:

  1. The GOTCHAS section is the highest-value content. Each gotcha names the
     SYMPTOM, explains the CAUSE, and implies the FIX. These are the things a
     capable model would still get wrong because they are non-obvious and
     specific to this problem, not derivable from general knowledge.

  2. Explain the WHY. Frontier models have good theory of mind; rote steps waste
     them. The transferable value is the reasoning behind what worked.

  3. Dead ends are uplift. A strong model can find the happy path; what it cannot
     know is which promising-looking approaches FAIL and why, which saves it from
     wasting moves. So we surface the approaches tried and why each failed as
     "what not to do."

  4. Transferable, not narrative. The skill must read as procedure for the NEXT
     person hitting this class of problem, not as a diary of this session.

  5. A frontmatter description that states what it does AND when to use it, so a
     skills-compatible agent triggers it on the right tasks.

This module takes the structured extraction (which the model is good at) and
assembles the prose into the skill shape (which is mechanical and should not be
left to the model to format consistently).
"""

from __future__ import annotations

import re
from typing import Any


def _slugify(text: str, fallback: str = "session-skill") -> str:
    s = re.sub(r"[^a-z0-9]+", "-", str(text).lower()).strip("-")
    return s or fallback


def _title_from_themes(themes: list, problem_hint: str) -> str:
    if themes:
        return " / ".join(t.strip() for t in themes[:3])
    return problem_hint or "Debugging session"


def _infer_problem(extraction: dict) -> str:
    """A one-line statement of the problem class this skill addresses."""
    themes = extraction.get("themes", []) or []
    dead = extraction.get("dead_ends", []) or []
    breaks = extraction.get("breakthroughs", []) or []
    if breaks:
        w = breaks[-1].get("what_worked", "") if isinstance(breaks[-1], dict) else ""
        if w:
            return f"Solving the kind of problem where the fix is: {w.strip().rstrip(chr(46))}."
    if themes:
        return f"Working through a {', '.join(themes[:2])} problem."
    return "Working through a technical problem that took several attempts."


def _build_description(extraction: dict, problem: str) -> str:
    """Frontmatter description: what it does + when to trigger. Slightly pushy,
    per skill-creator guidance, because agents tend to under-trigger."""
    themes = extraction.get("themes", []) or []
    gotchas = extraction.get("gotchas", []) or []
    trig = ""
    if themes:
        trig = (
            f" Use this whenever a task involves {', '.join(themes[:3])}, "
            f"or when you hit symptoms similar to the gotchas below, even if the "
            f"user does not name them explicitly."
        )
    g = f" Captures {len(gotchas)} specific gotcha(s) that are easy to get wrong." if gotchas else ""
    return (
        f"Hard-won procedure for: {problem.rstrip('.')}.{g}{trig}"
    ).strip()


def _approaches_block(extraction: dict) -> str:
    """What was tried and why it FAILED — i.e. what NOT to do, with reasons.

    This is uplift: a capable model can find a path, but cannot know which
    promising approaches are dead ends without being told.
    """
    approaches = extraction.get("approaches_tried", []) or []
    if not approaches:
        return (
            "_No failed approaches were recorded for this session — it went "
            "straight to a working solution._"
        )
    lines = [
        "These approaches were tried and did NOT work. Avoid repeating them, or "
        "understand why they fail before reaching for them again:\n"
    ]
    for a in approaches:
        if not isinstance(a, dict):
            continue
        ap = str(a.get("approach", "")).strip()
        why = str(a.get("why_it_failed", "")).strip().rstrip(".")
        if ap:
            lines.append(f"- **{ap}** — fails because {why}." if why else f"- **{ap}** — did not work.")
    return "\n".join(lines)


def _gotchas_block(extraction: dict) -> str:
    """The highest-value section. Symptom -> cause -> implied fix.

    We reshape each raw gotcha string into the symptom/cause/fix frame where the
    text allows; if the gotcha is terse, we still present it as a watch-out with
    a prompt to check for it, because naming the trap is itself the value.
    """
    gotchas = extraction.get("gotchas", []) or []
    if not gotchas:
        return "_No specific gotchas were recorded for this session._"
    lines = [
        "These are the non-obvious traps from this problem — the things that are "
        "easy to get wrong and costly to rediscover. Check each one before "
        "assuming the obvious approach is safe:\n"
    ]
    # Phase 1 (RuleShaping arXiv:2604.11088): under each gotcha, emit a negative,
    # preferably state-dependent guardrail — the only individually beneficial rule
    # type. Deterministic + content-preserving (never fabricates a cause), so this
    # adds zero model calls and cannot invent anything not in the gotcha.
    try:
        from rule_phrasing import to_negative_constraint, is_negative_constraint
    except Exception:
        to_negative_constraint = None
        is_negative_constraint = None
    for g in gotchas:
        g = str(g).strip().rstrip(".")
        if not g:
            continue
        lines.append(f"- {g}.")
        if to_negative_constraint is not None:
            rule = to_negative_constraint(g)
            if (rule and rule.rstrip(".").lower() != g.lower()
                    and is_negative_constraint(rule)):
                lines.append(f"  - **Guardrail:** {rule}")
    return "\n".join(lines)


def _breakthrough_block(extraction: dict) -> str:
    breaks = extraction.get("breakthroughs", []) or []
    if not breaks:
        return "_No single breakthrough was recorded; progress was incremental._"
    lines = ["What actually worked, and the reasoning that makes it transferable:\n"]
    for b in breaks:
        if not isinstance(b, dict):
            continue
        w = str(b.get("what_worked", "")).strip().rstrip(".")
        if w:
            lines.append(f"- {w}.")
    return "\n".join(lines)


def _principles_block(extraction: dict) -> str:
    """Distill transferable principles from the arc. This is the 'why' layer."""
    approaches = extraction.get("approaches_tried", []) or []
    gotchas = extraction.get("gotchas", []) or []
    breaks = extraction.get("breakthroughs", []) or []
    out = []
    if approaches and breaks:
        out.append(
            "- The working solution came only after the failed approaches above. "
            "If you are reaching for one of those first, reconsider."
        )
    if gotchas:
        out.append(
            "- Most of the difficulty here was not the main logic but the "
            "edge conditions in the gotchas. Budget attention there."
        )
    if not out:
        out.append(
            "- This session was straightforward; the main value is the working "
            "approach recorded below."
        )
    return "\n".join(out)




def _is_terse(text: str) -> bool:
    """A gotcha is terse (low-value) if it's short and lacks a cause/fix signal."""
    t = str(text).strip()
    if len(t.split()) <= 6:
        return True
    # no causal/fix language -> probably just a label
    signals = ("because", "since", "so ", "instead", "fix", "use ", "avoid",
               "must", "should", "results in", "leads to", "causes", ";")
    return not any(sig in t.lower() for sig in signals)



# Phrases from illustrative examples that must never appear in real output —
# if they do, the model leaked the example instead of expanding the real gotcha.
_LEAK_MARKERS = (
    "reverse-bfs", "count_of_uncolored", "subtree_root", "leaf nodes first",
    "number_of_uncolored_children", "process deepest-first",
)


def _looks_leaked(text: str) -> bool:
    t = str(text).lower()
    return any(marker in t for marker in _LEAK_MARKERS)


def enrich_gotchas(extraction: dict, complete=None) -> dict:
    """Optionally expand terse gotchas into symptom/cause/fix form via one model
    call. `complete` is a function (prompt:str) -> str. If None, or if no terse
    gotchas, returns the extraction unchanged.

    This is the optional depth pass: the better extraction prompt handles most
    cases; this rescues sessions where the model still emitted thin labels.
    """
    gotchas = extraction.get("gotchas", []) or []
    if not complete or not gotchas:
        return extraction
    terse = [g for g in gotchas if _is_terse(g)]
    if not terse:
        return extraction

    themes = ", ".join(extraction.get("themes", []) or []) or "this problem"
    approaches = extraction.get("approaches_tried", []) or []
    ctx_lines = []
    for a in approaches:
        if isinstance(a, dict) and a.get("approach"):
            ctx_lines.append(f"- tried {a['approach']}: {a.get('why_it_failed','')}")
    ctx = "\n".join(ctx_lines)

    prompt = (
        "You are sharpening the gotchas in a coding skill file so they give a "
        "capable engineer real, non-obvious help.\n\n"
        f"PROBLEM AREA: {themes}\n"
        f"WHAT WAS TRIED AND FAILED:\n{ctx}\n\n"
        "Your job: rewrite each terse gotcha below into ONE self-contained "
        "sentence that names the symptom, the cause, and what to do instead. "
        "CRITICAL RULES:\n"
        "- Each rewritten gotcha MUST be specific to the problem area above "
        f"({themes}). Do NOT invent details from other domains.\n"
        "- Base the rewrite ONLY on the terse gotcha's own meaning plus the "
        "problem area. If you cannot rescue it without inventing facts, return it "
        "UNCHANGED.\n"
        "- Return ONLY a JSON array of strings, same length and order as the "
        "input. No prose, no code fences.\n\n"
        "Terse gotchas to rewrite:\n"
        + "\n".join(f"- {g}" for g in terse)
    )

    try:
        import json
        raw = complete(prompt)
        raw = raw.strip()
        # strip code fences if present
        import re as _re
        raw = _re.sub(r"^```(?:json)?|```$", "", raw, flags=_re.MULTILINE).strip()
        expanded = json.loads(raw)
        if isinstance(expanded, list) and len(expanded) == len(terse):
            # map terse -> expanded, but REJECT any expansion that leaked the
            # example phrasing (keep the original terse gotcha in that case).
            cleaned = []
            for original, exp in zip(terse, expanded):
                exp = str(exp).strip()
                if exp and not _looks_leaked(exp):
                    cleaned.append((original, exp))
                else:
                    cleaned.append((original, original))
            mapping = dict(cleaned)
            extraction = dict(extraction)
            extraction["gotchas"] = [mapping.get(g, g) for g in gotchas]
    except Exception:
        pass  # never let enrichment break the pipeline
    return extraction


def build_skill_md(extraction: dict) -> str:
    """Assemble a transferable SKILL.md from the structured extraction."""
    themes = extraction.get("themes", []) or []
    problem = _infer_problem(extraction)
    title = _title_from_themes(themes, problem)
    name = _slugify(title)
    description = _build_description(extraction, problem)

    tags = ", ".join(themes) if themes else "debugging, problem-solving"

    md = f"""---
name: {name}
description: {description}
---

# {title}

## When this applies

{problem} Use the procedure below when you hit this class of problem, especially
if the symptoms match the gotchas section — that is where this skill earns its
place over solving from scratch.

## What does NOT work (and why)

{_approaches_block(extraction)}

## What works

{_breakthrough_block(extraction)}

## Gotchas (read this first)

{_gotchas_block(extraction)}

## Transferable principles

{_principles_block(extraction)}

## Tags

{tags}
"""
    return md


# Backwards-compatible section check used by extract.py's validator
SKILL_SECTIONS = (
    "When this applies",
    "What does NOT work",
    "What works",
    "Gotchas",
    "Transferable principles",
    "Tags",
)


if __name__ == "__main__":
    sample = {
        "themes": ["graph theory", "dynamic programming"],
        "approaches_tried": [
            {"approach": "naive recursion", "why_it_failed": "recomputes the same subgraphs exponentially"},
            {"approach": "BFS from each node", "why_it_failed": "O(V^2) blew the time limit on dense graphs"},
        ],
        "dead_ends": [
            {"position": 0.3, "what_happened": "recursion stack overflowed on the big case"},
        ],
        "breakthroughs": [
            {"position": 0.85, "what_worked": "memoized the subgraph results keyed by visited-set bitmask"},
        ],
        "gotchas": [
            "the bitmask must include the start node or you double-count paths",
            "Python recursion limit hits before the logic is wrong, so raise it early to see the real bug",
        ],
        "sentiment_arc": {"start": "frustrated", "end": "resolved"},
    }
    print(build_skill_md(sample))
