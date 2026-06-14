"""
Run the distractor-trap eval against a real frontier model via OpenRouter.

This tests the slug's REAL value proposition: does the skill's negative knowledge
(the documented trap) steer a frontier model away from the tempting wrong approach
it would otherwise take? This is the gap a frontier model cannot fill from weights.

PREREQS (never hardcode the key):
    export OPENROUTER_API_KEY=sk-or-...
    export EVAL_ANSWERER_MODEL=anthropic/claude-opus-4.6   # optional override
Run from the repo root (imports the real skill_builder):
    python run_distractor_eval.py
"""

from __future__ import annotations

import sys

from openrouter_client import make_completer, verify_models, DEFAULT_ANSWERER_MODEL, DEFAULT_GRADER_MODEL
from distractor_eval import DISTRACTOR_JUDGE_SYSTEM
from distractor_eval import run_distractor_eval
from distractor_cases import CASES


def main() -> int:
    model = DEFAULT_ANSWERER_MODEL
    grader_model = DEFAULT_GRADER_MODEL
    if model == grader_model:
        print("WARNING: answerer and grader are the same model; set EVAL_GRADER_MODEL "
              "to a different model to keep the judge independent.")
    print(f"Verifying models live on OpenRouter...")
    status = verify_models(model, grader_model)
    for mid, ok in status.items():
        print(f"  {mid}: {'OK' if ok is True else ok}")
    if not all(v is True for v in status.values()):
        print("Set EVAL_ANSWERER_MODEL / EVAL_GRADER_MODEL to current ids (https://openrouter.ai/models).")
        return 1

    # Low temperature: we want the model's DEFAULT instinct, not creative variance.
    answerer = make_completer(model, temperature=0.1, max_tokens=700)
    grader = make_completer(grader_model, system=DISTRACTOR_JUDGE_SYSTEM,
                            temperature=0.0, max_tokens=200)

    print("\n--- Running distractor-trap eval ---")
    print("(does the skill steer the model away from the tempting wrong approach?)")
    print(f"answerer: {model}   judge: {grader_model}")
    rep = run_distractor_eval(CASES, answerer, grader, out_dir="./distractor_runs")

    print("\n========== RESULT ==========")
    print(f"answerer: {model}")
    print(f"cases scored: {rep['n_scored']}  (leaked excluded: {rep['n_leaked_excluded']})")
    print(f"trap-avoidance WITHOUT skill: {rep['no_skill_avoidance_rate']}")
    print(f"trap-avoidance WITH skill:    {rep['with_skill_avoidance_rate']}")
    print(f"AVOIDANCE UPLIFT:             {rep['avoidance_uplift']}")
    print(f"rescues (trapped->avoided):   {rep['rescues']}")
    print(f"regressions (avoided->trapped): {rep['regressions']}")
    print("\nper-case:")
    for r in rep["per_case"]:
        flag = " [LEAKED]" if r["leaked"] else ""
        print(f"  {r['name']}: without={r['no_skill_avoided']} with={r['with_skill_avoided']}{flag}")
        print(f"      without: {r['no_skill_detail']}")
        print(f"      with:    {r['with_skill_detail']}")
    print("\nraw answers saved to:", rep["raw_saved_to"])
    print("\nInterpretation:")
    print("  - rescues > 0  : the skill genuinely helped (model fell for the trap")
    print("                   unaided, avoided it with the skill). This is the slug's value.")
    print("  - uplift ~0, both already high : the frontier model didn't need the skill")
    print("                   for these traps (they were not hard enough). Report honestly.")
    print("  - regressions > 0 : the skill MISLED the model. Report this too.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
