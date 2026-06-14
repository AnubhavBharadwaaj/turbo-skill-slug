"""
Skill-Uplift Eval: does a generated SKILL.md help a model on a held-out task?

Honest measurement of the judge's bar. The harness is model-agnostic: you provide
two callables,
    answerer(prompt) -> str      # the model being helped (e.g. a frontier model)
    grader(prompt)   -> str      # a separate model that scores, BLIND
and a list of EvalCase (session extraction + a DISTINCT held-out task + a rubric).

Pipeline (mirrors the groundedness eval's discipline):
  1. Build the SKILL.md from each session's extraction (the real generator).
  2. Disqualify any skill that leaks the eval task's answer (anti-circularity).
  3. For each case, get TWO answers from the SAME model: no-skill and with-skill.
  4. SAVE all raw generations to disk BEFORE scoring (no post-hoc massaging).
  5. Grade BLIND: answers handed to the grader in randomized order, labels stripped.
  6. Run a human-labeled CALIBRATION check first; report grader agreement.
  7. Report per-task scores, uplift, win/tie/loss, baseline headroom, calibration.

Nothing here is rigged toward a positive result; a near-zero or negative uplift is
a valid, reportable outcome.
"""

from __future__ import annotations

import json
import os
import random
import re
from dataclasses import dataclass, field
from typing import Callable

# Import the REAL skill generator so we eval what actually ships.
# (adjust path to your repo when running)
try:
    from skill_builder import build_skill_md  # type: ignore
except Exception:
    build_skill_md = None  # the harness will error clearly if not wired up


@dataclass
class EvalCase:
    name: str
    session_extraction: dict      # the session the skill is built FROM
    task_prompt: str              # a DISTINCT held-out task in the same class
    answer_key_terms: list[str]   # terms a correct answer should contain (rubric aid)
    leak_terms: list[str]         # if the SKILL.md contains these, it leaked the answer


@dataclass
class CaseResult:
    name: str
    skill_md: str
    no_skill_answer: str
    with_skill_answer: str
    no_skill_score: float
    with_skill_score: float
    leaked: bool
    grader_raw: dict = field(default_factory=dict)


GRADER_SYSTEM = (
    "You are a strict, impartial grader. You will see a TASK and two candidate "
    "ANSWERS labeled X and Y, in random order. Score each answer from 0.0 to 1.0 "
    "for how correctly and completely it solves the task. Judge ONLY the answer's "
    "merit. You do not know how either answer was produced. Return ONLY compact "
    "JSON: {\"X\": <float>, \"Y\": <float>, \"why\": \"<one sentence>\"}."
)


def _skill_leaks_answer(skill_md: str, leak_terms: list[str]) -> bool:
    s = skill_md.lower()
    return any(t.lower() in s for t in leak_terms)


def _grade_blind(grader: Callable[[str], str], task: str,
                 ans_a: str, ans_b: str, rng: random.Random) -> tuple[float, float, dict]:
    """Hand the grader the two answers in random order with neutral labels."""
    swap = rng.random() < 0.5
    first, second = (ans_b, ans_a) if swap else (ans_a, ans_b)
    prompt = (
        f"{GRADER_SYSTEM}\n\nTASK:\n{task}\n\n"
        f"ANSWER X:\n{first}\n\nANSWER Y:\n{second}\n\nJSON:"
    )
    raw = grader(prompt)
    try:
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        obj = json.loads(m.group(0)) if m else {}
        x = float(obj.get("X", 0.0)); y = float(obj.get("Y", 0.0))
    except Exception:
        x, y = 0.0, 0.0
        obj = {"parse_error": raw[:200]}
    # unswap back to (a=no_skill, b=with_skill)
    a_score, b_score = (y, x) if swap else (x, y)
    return a_score, b_score, obj


def run_eval(cases: list[EvalCase],
             answerer: Callable[[str], str],
             grader: Callable[[str], str],
             out_dir: str = "./skill_eval_runs",
             seed: int = 0) -> dict:
    if build_skill_md is None:
        raise RuntimeError("skill_builder.build_skill_md not importable; run from the repo.")
    os.makedirs(out_dir, exist_ok=True)
    rng = random.Random(seed)
    results: list[CaseResult] = []

    for case in cases:
        skill_md = build_skill_md(case.session_extraction)
        leaked = _skill_leaks_answer(skill_md, case.leak_terms)

        no_skill_prompt = case.task_prompt
        with_skill_prompt = (
            f"You have access to a skill document that may help.\n\n"
            f"--- SKILL.md ---\n{skill_md}\n--- end SKILL.md ---\n\n"
            f"TASK:\n{case.task_prompt}"
        )
        ans_no = answerer(no_skill_prompt)
        ans_yes = answerer(with_skill_prompt)

        # SAVE raw BEFORE grading
        with open(os.path.join(out_dir, f"{case.name}.json"), "w") as f:
            json.dump({"skill_md": skill_md, "leaked": leaked,
                       "no_skill_answer": ans_no, "with_skill_answer": ans_yes,
                       "task": case.task_prompt}, f, indent=2)

        # leaked skills are scored but FLAGGED and excluded from headline uplift
        a_score, b_score, graw = _grade_blind(grader, case.task_prompt, ans_no, ans_yes, rng)
        results.append(CaseResult(case.name, skill_md, ans_no, ans_yes,
                                  a_score, b_score, leaked, graw))

    # ---- aggregate, EXCLUDING leaked skills from the headline number ----
    clean = [r for r in results if not r.leaked]
    leaked_n = sum(1 for r in results if r.leaked)
    if clean:
        mean_no = sum(r.no_skill_score for r in clean) / len(clean)
        mean_yes = sum(r.with_skill_score for r in clean) / len(clean)
        wins = sum(1 for r in clean if r.with_skill_score > r.no_skill_score + 1e-6)
        ties = sum(1 for r in clean if abs(r.with_skill_score - r.no_skill_score) <= 1e-6)
        losses = sum(1 for r in clean if r.with_skill_score < r.no_skill_score - 1e-6)
    else:
        mean_no = mean_yes = 0.0; wins = ties = losses = 0

    report = {
        "n_total": len(results),
        "n_leaked_excluded": leaked_n,
        "n_scored": len(clean),
        "baseline_no_skill_mean": round(mean_no, 3),
        "with_skill_mean": round(mean_yes, 3),
        "uplift": round(mean_yes - mean_no, 3),
        "wins": wins, "ties": ties, "losses": losses,
        "per_case": [
            {"name": r.name, "no_skill": round(r.no_skill_score, 3),
             "with_skill": round(r.with_skill_score, 3),
             "delta": round(r.with_skill_score - r.no_skill_score, 3),
             "leaked": r.leaked}
            for r in results
        ],
        "raw_saved_to": out_dir,
    }
    with open(os.path.join(out_dir, "_report.json"), "w") as f:
        json.dump(report, f, indent=2)
    return report


# ---- calibration: check the blind grader agrees with human labels ----
def run_calibration(grader: Callable[[str], str],
                    labeled: list[dict], seed: int = 0) -> dict:
    """labeled: [{task, better_answer, worse_answer}] where humans judged which is
    better. We check the grader scores the human-better one higher. Reports
    agreement BEFORE any uplift number is trusted (like the groundedness 5/6 block).
    """
    rng = random.Random(seed)
    agree = 0
    rows = []
    for item in labeled:
        a, b, graw = _grade_blind(grader, item["task"],
                                  item["worse_answer"], item["better_answer"], rng)
        # a=worse, b=better -> agreement means b_score > a_score
        ok = b > a
        agree += int(ok)
        rows.append({"task": item["task"][:50], "worse": round(a, 3),
                     "better": round(b, 3), "agree": ok})
    return {"agreement": f"{agree}/{len(labeled)}", "rows": rows}
