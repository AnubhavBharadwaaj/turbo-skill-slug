# Integrating the three phases into the live slug

All modules are dependency-light, frozen-model, and run on the Space. They reuse the
existing extraction and the OpenRouter/HF completer you already have.

## Files
- artifact_meta.py        Phase 1: lifecycle metadata (provenance/confidence/usage/validation)
- rule_phrasing.py        Phase 1: RuleShaping negative-constraint phrasing (LLM + deterministic fallback)
- session_store.py        Phase 2: store of past sessions (JSON; use the Modal volume in prod)
- gotcha_cluster.py       Phase 2: cluster recurring gotchas (embedding or LLM-judge backend)
- promotion_engine.py     Phase 2: promote recurring clusters -> validated L3 rules; demote on failure
- multi_analyst_extract.py Phase 3: Trace2Skill-style N-analyst recurrence merge (higher-fidelity extraction)

## Wiring (minimal)

1. After each session's extraction, persist it:
       store = SessionStore("/vol/gallery/sessions.json")   # Modal volume in prod
       store.add(session_id, extraction)

2. Phase 3 (optional, improves fidelity): replace single-pass gotcha extraction with
       gotchas = multi_analyst_gotchas(session_text, completer, n_analysts=4,
                                       had_errors=bool(extraction.get("dead_ends")),
                                       agree_min=2, judge_same=same_gotcha_judge)
   Cost knob: n_analysts (3–5 cheap; larger = higher fidelity, higher cost).

3. Phase 2 (the headline): run a promotion pass (cheap; do it after add, or on idle):
       rules = promote(
           store, k_threshold=3,
           cluster_fn=lambda items: cluster_by_judge(items, same_gotcha_judge),
           reshape_fn=lambda g: to_negative_constraint_llm(g, completer),
           validate_fn=rule_validates,          # reuse the distractor/novel eval harness
           require_human=False,                 # set True for the 10/10 human-gated path
       )
   Persist promoted rules (with their ArtifactMeta) alongside sessions.

4. Surface a new lens in the app: "the rules the slug has learned across your
   sessions" — list each L3 rule with its provenance (which sessions), confidence,
   and last-validated time. This is the lifecycle-governance story made visible.

## The validation gate (important — don't skip)
`validate_fn(rule_text, cluster)` should reuse the held-out check you already built
(distractor_eval / novel_eval): does an answer that APPLIES the rule beat one that
ignores it, on a task derived from the cluster? Promoting without this is how you
promote "compact noise" (the spectrum paper's exact warning). Gate-only is the
default; `require_human=True` adds confirmation for the 10/10 path.

## What to claim (honestly)
"Single self-generated skills give a frontier model ~0.0 uplift (our eval, matching
SkillsBench as cited in arXiv:2604.15877). We implement a working slice of that
paper's proposed solution — the 'missing diagonal' of adaptive upward compression:
the slug consolidates gotchas that recur across sessions into validated,
negative-constraint-phrased L3 rules (RuleShaping) carrying provenance/confidence/
lifecycle metadata, with demotion when a rule stops validating, and Trace2Skill-style
multi-analyst recurrence-merging for extraction fidelity. Honest limits: recurrence
is a proxy for value (mitigated by the validation gate + optional human confirmation);
small analyst-N is a cheaper approximation of Trace2Skill's 128."

---

## CORRECTIONS after reading the actual papers (not just the survey)

- Phase 3 was rebuilt as `trace2skill_faithful.py` after reading arXiv:2603.25158 in
  full. The first version (`multi_analyst_extract.py`) was a simplified guess that
  MISSED the paper's central mechanism: the error analyst is an AGENTIC, VALIDATION-
  GATED loop (it must produce a verified causal cause or the trace is EXCLUDED), not a
  single call. The paper shows the single-call version over-attributes parse errors as
  root cause in 57% of cases and hallucinates causes — i.e. the leak/false-cause bug.
  Consolidation is an LLM merge operator applied hierarchically with a prevalent-
  pattern bias; success patches are lower-trust; low-support items route to references/.
  Use `trace2skill_faithful.py`; keep `multi_analyst_extract.py` only as the simpler
  fallback if the agentic loop is too costly on the Space.

- RuleShaping verified against arXiv:2604.11088 ("Do Agent Rules Shape or Distort?").
  Confirmed: +7–14pp, negative constraints the only beneficial type, positive
  directives hurt. Added nuance: rules work via CONTEXT PRIMING (random ~ curated),
  state-dependent process guardrails ("don't X until Y") are the highest-benefit
  category (63.8%), and rules are collectively helpful even when individually inert
  (no degradation up to 50). `rule_phrasing.py` now biases toward state-dependent
  negative guardrails.

## REMAINING GAPS (do not overclaim)

1. CLUSTERING IS UNVALIDATED ON REAL DATA. The promotion engine works when the
   "same underlying gotcha" judge is good. On arbitrary messy sessions, clustering
   quality is unknown — a bad judge promotes noise or misses recurrences. This is the
   biggest open risk and needs a real embedding/LLM judge tested on labeled session data.

2. THE ERROR-ANALYST VALIDATION GATE is faithful in STRUCTURE but ADAPTED: the paper
   runs a minimal fix against ground truth in a sandbox. A narrated coding session fed
   to the slug usually has no ground truth / sandbox, so we use strict self-verification
   (cite trace evidence) instead. This is weaker than the paper's executable gate and
   should be labeled as an adaptation, not a reproduction.

3. NO END-TO-END RUN ON REAL SLUG SESSIONS YET. Everything is validated on controlled/
   realistic-but-synthetic data. Whether real slug sessions cluster usefully is untested.
