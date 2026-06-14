# Skill-Uplift Eval Report

> Fill this in with the ACTUAL numbers from `run_skill_eval.py`. The template is
> written so an honest result is the easy result. Do not delete the caveats.

## Setup
- Answerer model: `<EVAL_ANSWERER_MODEL>`
- Grader model (blind, different vendor): `<EVAL_GRADER_MODEL>`
- Skill generator: the shipped `skill_builder.build_skill_md`
- Cases: N = `<n_scored>` (held-out tasks, each a DISTINCT problem in the same
  class as its source session; leaked skills excluded: `<n_leaked_excluded>`)
- Raw generations saved: `skill_eval_runs/` (anyone can re-score)

## Grader calibration (run BEFORE trusting the uplift)
- Agreement with human labels: `<X/Y>`
- If agreement is low, the uplift number is unreliable; say so explicitly.

## Result
| condition | mean score |
|---|---:|
| no skill (baseline) | `<baseline_no_skill_mean>` |
| with skill | `<with_skill_mean>` |
| **uplift** | **`<uplift>`** |

- Win / tie / loss across cases: `<wins>` / `<ties>` / `<losses>`
- Per-case deltas: `<paste from runner>`

## Honest reading (write the true one)
Pick the sentence that matches the data; do not overstate:
- Positive & consistent: "The generated skill produced measurable uplift
  (+`<uplift>`) on held-out tasks in the same class, winning `<wins>`/`<n>`."
- Small/mixed: "The skill produced small, inconsistent uplift (+`<uplift>`);
  it helped on `<wins>` cases and was neutral/negative on the rest."
- Near-zero: "On this set, the skill did not produce measurable uplift over the
  frontier baseline. The baseline was already strong (`<baseline>`), leaving
  little headroom; a harder task set would test this better."

## Caveats (keep all that apply)
- Small N; indicative, not a benchmark (same posture as the 25-transcript
  groundedness eval).
- Single grader model; blinding reduces but does not remove grader bias, hence
  the calibration check above.
- Uplift depends on task difficulty: where the baseline already scores ~1.0 there
  is no room to show uplift. Baseline headroom is reported so this is visible.
- Skills that leaked the task answer were excluded (`<n_leaked_excluded>`),
  not silently scored.
