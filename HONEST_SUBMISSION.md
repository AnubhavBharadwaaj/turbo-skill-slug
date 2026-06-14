# Honest Submission Notes — TurboSkillSlug

This document is the unvarnished account of what TurboSkillSlug actually does,
what is genuinely strong, what is partial, and what is aspirational. If a claim
is not in here with its caveats, treat the marketing copy as marketing.

Demo video: https://youtu.be/qSP9olWRv7o
Space: https://huggingface.co/spaces/build-small-hackathon/TurboSkillSlug
Code: https://github.com/AnubhavBharadwaaj/turbo-skill-slug

## What it does, honestly

You give the slug a build session two ways: narrate it aloud (audio), or drop a
Claude Code / Codex CLI session trace (`.jsonl`). It transcribes/parses, extracts
a structured record, and returns four artifacts: a grounded second-person recap
in a fine-tuned "slug voice," a SKILL.md, a procedural SVG shell, and a thermal
receipt. The shell is born on screen as a scroll unrolling along its spiral arm.

## What is genuinely strong

- **Two custom 1.5B LoRA adapters, both published and both used.** Voice
  (500 pairs, loss 0.89) and extraction (167 pairs, loss 0.81). The extraction
  LoRA replaced a prompted Qwen-7B, bringing the primary pipeline to ~2.6B active
  params (Whisper 809M + one 1.5B base serving both adapters on a single T4).
- **The groundedness eval is real and published with its raw data.** On 25
  held-out transcripts the fine-tuned 1.5B reaches semantic groundedness 0.76 vs
  the 7B's 0.72, at a third the active size, by paraphrasing rather than copying.
- **The shell is fully procedural and traceable.** Every visual element derives
  from a real session feature: dead ends are knots, gotchas are jewels, the
  breakthrough is the aperture, sentiment is the color arc. No image generation.
- **Trace input works.** A real Claude Code or Codex session log runs through the
  same pipeline as audio. Judges can feed their own logs.

## What is partial or has real caveats

- **Extraction parse reliability: 21/25 vs the 7B's 24/25.** The smaller model
  produces invalid JSON more often. In the app a brace-walking parser and field
  validators recover most of this, but the raw rate is a real cost of going
  small, and we report it unsoftened.
- **The groundedness metric is calibrated to 5/6, not 6/6.** A hand-labeled
  calibration block (run before scoring, printed in the logs) missed one case:
  a grounded paraphrase scored just under threshold. The miss understates the
  LoRA rather than inflating it, but the metric is not perfectly calibrated and
  we do not claim it is. 25 transcripts is a small sample; treat the LoRA-vs-7B
  gap as "matches or slightly exceeds," not "beats."
- **SKILL.md quality depends on extraction quality.** A good session yields
  transferable gotchas (symptom/cause/fix). A thin session yields thinner
  gotchas. An optional one-shot enrichment pass expands terse gotchas, but it is
  best-effort: if the model returns something off, a guard keeps the original.
  We caught and fixed a real bug where few-shot examples in the enrichment prompt
  leaked into output; the guard now rejects any leaked phrasing.
- **The scroll-unroll animation ships ~1.7MB per shell** (14 stacked growth
  stages, so the parchment can lay down along the spiral arm rather than as a
  radial wipe). It is browser-rendered via SMIL inside an iframe, with a "watch
  it unroll again" replay. On a slow connection the first paint takes a beat.
  If SMIL fails to run, the figures and shell still show (nothing is hard-hidden);
  the animation is enhancement, not a dependency.
- **The 3D paper curl rides the spiral tip via animateMotion.** Verified
  frame-by-frame in offline renders; exact tip-tracking in every browser is the
  part most likely to need a small timing tweak.

## What is aspirational / not built

- **Shell gallery with permalinks** is a stretch goal; if it is in the submitted
  build it is freshly added and lightly tested.
- **Session diff view** (compare two sessions' shells) is not built.
- **Closing the parse-rate gap** needs more training pairs and constrained
  decoding; not done.

## Infrastructure honesty

- The Qwen-7B still exists in the codebase but ONLY as a labeled fallback when a
  Modal endpoint is briefly unavailable. The primary path is the 1.5B dual
  adapter. The architecture table in the README reflects this.
- The dual-adapter server can hold one warm container for demo reliability
  (~$0.60/hr). It should be stopped after judging (`modal app stop
  slug-dual-serve`).

## How to verify our claims

- Groundedness: `modal run semantic_eval.py` reproduces the table; raw
  generations are published in the eval dataset so anyone can re-score.
- Trace input: drop the sample `.jsonl` (one click) or your own session log.
- Models: both LoRA adapters are public on the Hub.
- Shell traceability: change a session's sentiment or dead-end count and watch
  the shell's colors and knots change accordingly.

## The one-sentence honest summary

A small, slow, genuinely ~2.6B pipeline that turns a coding session into a
grounded recap, a transferable skill, and a procedural shell, measured honestly
(including where the small model costs us), with every model and the eval data
published for anyone to check.
