"""
Distractor-trap eval: does the skill steer a frontier model AWAY from the tempting
wrong approach it would otherwise take?

Scoring is two-layer and deliberately objective-first:

  1. SIGNATURE score (objective, no model judgment): scan the answer for trap vs
     correct signatures. trap_present and correct_present are booleans. The
     "avoided-trap" score = correct_present AND NOT trap_present.

  2. BLIND QUALITY score (a separate model, optional backstop): only to confirm
     the correct-signature answer is actually a good answer, not a false positive.

The headline metric is the AVOIDANCE RATE: how often the model avoided the trap
WITH the skill vs WITHOUT. This is the thing a frontier model genuinely cannot get
from weights alone — knowledge of which tempting path is a dead end in context.

Raw answers are saved before scoring. Leaked skills are excluded.
"""

from __future__ import annotations

import json
import os
import re

try:
    from skill_builder import build_skill_md
except Exception:
    build_skill_md = None


from dataclasses import dataclass, field


@dataclass
class DistractorCase:
    """A task whose OBVIOUS approach is wrong; the skill's gotcha warns of the trap."""
    name: str
    session_extraction: dict      # the session the skill is built FROM
    task_prompt: str              # task whose naive solution is the trap
    trap_signature: list          # (legacy heuristic, retained for reference)
    correct_signature: list       # (legacy heuristic, retained for reference)
    leak_terms: list = field(default_factory=list)  # skill leaked the task answer
    trap_desc: str = ""           # plain description of the trap, for the LLM judge
    correct_desc: str = ""        # plain description of the correct approach



DISTRACTOR_JUDGE_SYSTEM = (
    "You are a strict, impartial code reviewer. You will see a TASK, a description "
    "of a KNOWN TRAP (a tempting but wrong approach), the CORRECT approach, and ONE "
    "candidate ANSWER. Decide what the answer ACTUALLY RECOMMENDS as its primary "
    "solution. Mentioning the trap in order to WARN against it is GOOD, not a "
    "failure. Return ONLY compact JSON: "
    '{"primary": "trap" | "correct" | "unclear", '
    '"warns_about_trap": true|false, '
    '"why": "<one sentence>"}'
)


def _judge_answer(grader, task, trap_desc, correct_desc, answer):
    prompt = (
        f"{DISTRACTOR_JUDGE_SYSTEM}\n\nTASK:\n{task}\n\n"
        f"KNOWN TRAP (tempting but wrong): {trap_desc}\n"
        f"CORRECT approach: {correct_desc}\n\n"
        f"ANSWER:\n{answer}\n\nJSON:"
    )
    raw = grader(prompt)
    try:
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        obj = json.loads(m.group(0)) if m else {}
    except Exception:
        obj = {"primary": "unclear", "warns_about_trap": False, "parse_error": raw[:200]}
    obj["avoided"] = (obj.get("primary") == "correct")
    return obj


def _has_any(text: str, needles: list[str]) -> bool:
    t = text.lower()
    return any(n.lower() in t for n in needles)


def _avoided_trap(answer: str, trap_sig: list[str], correct_sig: list[str]) -> dict:
    trap = _has_any(answer, trap_sig)
    correct = _has_any(answer, correct_sig)
    # avoided = used the correct approach AND did not lead with the trap
    avoided = correct and not trap
    return {"trap_present": trap, "correct_present": correct, "avoided": avoided}


def run_distractor_eval(cases, answerer, grader, out_dir="./distractor_runs", seed=0):
    if build_skill_md is None:
        raise RuntimeError("skill_builder.build_skill_md not importable; run from the repo.")
    os.makedirs(out_dir, exist_ok=True)
    rows = []
    for case in cases:
        skill_md = build_skill_md(case.session_extraction)
        leaked = _has_any(skill_md, case.leak_terms)

        no_skill_ans = answerer(case.task_prompt)
        with_skill_ans = answerer(
            "You have access to a skill document that may help.\n\n"
            f"--- SKILL.md ---\n{skill_md}\n--- end SKILL.md ---\n\n"
            f"TASK:\n{case.task_prompt}"
        )

        with open(os.path.join(out_dir, f"{case.name}.json"), "w") as f:
            json.dump({"skill_md": skill_md, "leaked": leaked,
                       "no_skill": no_skill_ans, "with_skill": with_skill_ans,
                       "task": case.task_prompt}, f, indent=2)

        td = case.trap_desc or "the naive/obvious approach"
        cd = case.correct_desc or "the non-obvious correct approach"
        ns = _judge_answer(grader, case.task_prompt, td, cd, no_skill_ans)
        ws = _judge_answer(grader, case.task_prompt, td, cd, with_skill_ans)
        rows.append({"name": case.name, "leaked": leaked,
                     "no_skill_avoided": ns["avoided"], "with_skill_avoided": ws["avoided"],
                     "no_skill_detail": ns, "with_skill_detail": ws})

    clean = [r for r in rows if not r["leaked"]]
    n = len(clean)
    ns_rate = sum(r["no_skill_avoided"] for r in clean) / n if n else 0
    ws_rate = sum(r["with_skill_avoided"] for r in clean) / n if n else 0
    # "rescues": cases the skill FLIPPED from trapped -> avoided
    rescues = sum(1 for r in clean if r["with_skill_avoided"] and not r["no_skill_avoided"])
    regressions = sum(1 for r in clean if not r["with_skill_avoided"] and r["no_skill_avoided"])

    report = {
        "n_scored": n, "n_leaked_excluded": len(rows) - n,
        "no_skill_avoidance_rate": round(ns_rate, 3),
        "with_skill_avoidance_rate": round(ws_rate, 3),
        "avoidance_uplift": round(ws_rate - ns_rate, 3),
        "rescues": rescues, "regressions": regressions,
        "per_case": rows, "raw_saved_to": out_dir,
    }
    with open(os.path.join(out_dir, "_report.json"), "w") as f:
        json.dump(report, f, indent=2)
    return report
