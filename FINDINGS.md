# When does a SKILL.md actually help a 2026 frontier model? (measured)

Three blind, calibrated evals against `anthropic/claude-opus-4.6` (answerer) and
`openai/gpt-5.1` (independent judge). Raw generations saved; method below.

## The result in one table

| Skill content | Held-out task class | Avoidance / score WITHOUT skill | WITH skill | Uplift |
|---|---|---:|---:|---:|
| General algorithmic procedure | standard tree-DP, Markov absorption | 1.0 | 1.0 | **0.0** |
| Well-known engineering traps | Kahan summation, check-then-act race, N+1 query | 1.0 | 1.0 | **0.0** |
| Novel / non-public rules | fictional APIs (zthrumdb fence, qbucket reset, flazon reversal) | 0.0 | 1.0 | **+1.0** |

3 rescues, 0 regressions in the novel-trap condition. Grader calibration 3/3.

## What this means (the actual finding)

A frontier model's weights already contain the public, written-down corpus of
software knowledge. A skill file that repeats any of it gives **zero** uplift,
confirmed twice, on both easy tasks and famous footguns the model handles unaided.

A skill file gives **large** uplift exactly when it carries knowledge that could
NOT have been in the training data: private/proprietary system behavior, post-cutoff
facts, project-specific conventions, or genuinely novel discoveries. The dividing
line is not task difficulty. It is **whether the knowledge could have been public.**

### A second, sharper observation from the raw data

In the unaided novel cases, the model did not just answer wrong, it often went
**"unclear": it hedged, asked for clarification, or refused to use the unknown API.**
A frontier model senses when it lacks the knowledge and stalls. The skill does not
merely correct wrong answers; it **unblocks the model on systems it otherwise cannot
act on at all.** That is the higher-value case: not "answer better," but "able to
proceed where it was previously stuck."

## Why this is the honest, useful framing for TurboSkillSlug

The slug's value is NOT in summarizing a session of standard work, that produces a
skill the model ignores (uplift 0.0). The value is in capturing the **negative,
private, non-obvious knowledge** from a real session: the trap specific to this
codebase, the undocumented behavior, the dead end that cost an hour. Fed that, the
generated SKILL.md measurably changes a frontier model's behavior (+1.0).

This is a sharper claim than "skills help," and we can defend every part of it with
data and published raw outputs.

## Method (anti-self-deception safeguards)

- Held-out tasks DISTINCT from the source session (transfer, not memorization).
- Blind judge: a DIFFERENT vendor's model, scoring the answer's PRIMARY
  recommendation, with "warns about the trap then gives the fix" counted as CORRECT.
  (An earlier signature-matching scorer was discarded because it miscounted
  warnings as failures; the LLM judge fixed this. We report the correction.)
- Leak guard: any skill containing the literal task answer is excluded.
- Calibration run before trusting numbers (grader agreed with human labels 3/3).
- Raw generations saved before scoring; small N, reported as indicative not a benchmark.

## Honest limitations

- Small N (2-3 per condition). Indicative, not a benchmark. The effect sizes
  (0.0 vs 1.0) are large and consistent, but the sample is small.
- Single answerer + single judge model. Blinding and a cross-vendor judge reduce
  but do not eliminate model-specific effects.
- The novel cases are fictional by necessity (to guarantee non-derivability); they
  stand in for real private/proprietary knowledge, which is the production case.
