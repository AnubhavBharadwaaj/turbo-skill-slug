# Skill-Uplift Eval — methodology (read before trusting any number)

## The claim we are testing

A generated SKILL.md gives a capable LLM real uplift on a *related future task*,
over that same model solving the task with no skill. This is the judge's bar:
"useful even to a frontier model that is already capable without it."

## Why this is hard to measure honestly (and how we handle each trap)

1. **Confounding by model strength.** A strong model may ace the task with or
   without the skill, hiding any uplift. We pick tasks at the *edge* of the
   model's ability (it sometimes fails them unaided), where a skill can move the
   needle. We report the unaided baseline pass rate so the headroom is visible.

2. **Leakage / circularity.** If the eval task is the *same* problem the skill was
   built from, the skill is just an answer key — meaningless. So the held-out task
   is a DIFFERENT problem in the SAME class as the session. The skill must
   transfer, not memorize. We state the session→task pairing explicitly.

3. **Grader bias.** A grader that sees which answer used the skill will favor it.
   The grader is BLIND: it receives the two answers in randomized order with the
   condition labels stripped, and judges only correctness/quality.

4. **Cherry-picking.** We fix the task set and the sessions BEFORE running, list
   them here, and report every item including failures. No post-hoc dropping.

5. **The "skill is just hints" objection.** A skill that smuggles the answer is not
   uplift, it's cheating. We verify each skill contains transferable PROCEDURE
   (gotchas, what-not-to-do), not the specific solution to the eval task. Any
   skill whose gotchas name the eval task's exact answer is disqualified and noted.

## Design

- N sessions, each paired with a DISTINCT held-out task in the same problem class.
- For each task, the SAME model answers twice:
    A) NO-SKILL: task only.
    B) WITH-SKILL: task + the SKILL.md generated from the paired session.
  Order of which is generated first is irrelevant (separate calls), but the two
  answers are handed to the grader in RANDOM order with labels stripped.
- A blind grader (a separate strong model) scores each answer 0..1 on task success,
  not knowing which had the skill. We also run a small HUMAN-labeled calibration
  set first (like the groundedness eval) to check the grader agrees with us.
- Uplift = mean(with_skill_score) - mean(no_skill_score). We report:
    - per-task scores (both conditions),
    - the unaided baseline (headroom),
    - the win/tie/loss count (how often skill helped / didn't / hurt),
    - the calibration agreement,
    - and the raw generations, saved to disk, so anyone can re-score.

## What an honest result looks like

We commit IN ADVANCE to reporting the number as-is. Possible honest outcomes:
  - Clear positive uplift -> the skill works; report it.
  - Near-zero uplift -> the skill is pleasant but not load-bearing; say so.
  - Negative on some tasks -> the skill sometimes misleads; report which and why.
Any of these is a credible result. Only a hidden or massaged number is not.

## Honest limitations (stated up front)

- Small N. This is an indicative eval, not a benchmark. We report N and treat the
  result as directional, exactly as we did with the 25-transcript groundedness eval.
- Single grader model. Grader bias is reduced by blinding but not eliminated; the
  calibration set is how we keep ourselves honest about it.
- Task-class choice matters. We pick classes where a skill *could* plausibly help
  (procedural/gotcha-heavy domains); we do not claim uplift on trivia.
