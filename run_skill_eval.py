"""
Run the skill-uplift eval against real frontier models via OpenRouter.

PREREQUISITES (do these first; never hardcode the key):
    export OPENROUTER_API_KEY=sk-or-...
    # optional overrides if the catalog has moved:
    export EVAL_ANSWERER_MODEL=anthropic/claude-opus-4.6
    export EVAL_GRADER_MODEL=openai/gpt-5.1
Run from your repo root so it imports the REAL skill_builder.build_skill_md:
    python run_skill_eval.py

It will: verify the models are live -> run grader calibration -> run the eval ->
write skill_eval_runs/_report.json and print a plain-language summary. It reports
whatever number comes out. A modest or zero uplift is a valid, honest result.
"""

from __future__ import annotations

import json
import sys

from openrouter_client import (
    make_completer, verify_models,
    DEFAULT_ANSWERER_MODEL, DEFAULT_GRADER_MODEL,
)
from skill_uplift_eval import run_eval, run_calibration, GRADER_SYSTEM
from sample_cases import CASES

# A tiny human-labeled calibration set: pairs where WE judged which answer is
# better. The grader should agree. Swap in your own hand-labeled pairs.
CALIBRATION = [
    {
        "task": "Efficiently compute the sum of values on every root-to-leaf path's max in a tree.",
        "better_answer": "Do a single post-order (bottom-up) DFS; at each node combine the max of its children's results in O(n) total.",
        "worse_answer": "From each node, separately walk down every path to a leaf and take the max; simple but O(n^2) or worse.",
    },
    {
        "task": "Find the absorption probability in a Markov chain with two absorbing states.",
        "better_answer": "Write first-step equations for the transient states only, excluding absorbing rows, and solve the linear system.",
        "worse_answer": "Run a large Monte Carlo simulation and estimate the fraction of runs that end in the target state.",
    },
    {
        "task": "Avoid a stack overflow when recursing over a very deep tree in Python.",
        "better_answer": "Convert the recursion to an explicit stack/iterative form, or raise the recursion limit knowingly; the depth is the real cause.",
        "worse_answer": "Wrap the recursion in a try/except and hope it does not overflow.",
    },
]


def main() -> int:
    answerer_model = DEFAULT_ANSWERER_MODEL
    grader_model = DEFAULT_GRADER_MODEL
    if answerer_model == grader_model:
        print("WARNING: answerer and grader are the same model; pick different "
              "models to reduce self-grading bias (set EVAL_GRADER_MODEL).")

    print(f"Verifying models are live on OpenRouter...")
    status = verify_models(answerer_model, grader_model)
    for mid, ok in status.items():
        print(f"  {mid}: {'OK' if ok is True else ok}")
    if not all(v is True for v in status.values()):
        print("\nOne or more model ids are not in the live catalog. Set "
              "EVAL_ANSWERER_MODEL / EVAL_GRADER_MODEL to current ids "
              "(see https://openrouter.ai/models) and re-run.")
        return 1

    answerer = make_completer(answerer_model, temperature=0.2, max_tokens=900)
    grader = make_completer(grader_model, system=GRADER_SYSTEM,
                            temperature=0.0, max_tokens=300)

    print("\n--- Calibration (does the blind grader agree with human labels?) ---")
    cal = run_calibration(grader, CALIBRATION)
    print("grader agreement:", cal["agreement"])
    for row in cal["rows"]:
        print(f"  agree={row['agree']}  better={row['better']} worse={row['worse']}  {row['task']}")

    print("\n--- Running skill-uplift eval ---")
    report = run_eval(CASES, answerer, grader, out_dir="./skill_eval_runs")

    print("\n========== RESULT ==========")
    print(f"answerer: {answerer_model}   grader: {grader_model}")
    print(f"calibration: {cal['agreement']}")
    print(f"cases scored: {report['n_scored']}  (excluded as leaked: {report['n_leaked_excluded']})")
    print(f"baseline (no skill): {report['baseline_no_skill_mean']}")
    print(f"with skill:          {report['with_skill_mean']}")
    print(f"UPLIFT:              {report['uplift']}")
    print(f"win / tie / loss:    {report['wins']} / {report['ties']} / {report['losses']}")
    print("per-case:")
    for c in report["per_case"]:
        flag = " [LEAKED, excluded]" if c["leaked"] else ""
        print(f"  {c['name']}: no={c['no_skill']} with={c['with_skill']} Δ={c['delta']}{flag}")
    print("\nraw generations saved to:", report["raw_saved_to"])
    print("\nReport the number above as-is. Modest or zero uplift is a valid result.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
