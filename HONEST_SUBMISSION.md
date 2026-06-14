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
a structured record, and returns four artifacts: a transferable SKILL.md, a
grounded second-person recap in a fine-tuned "slug voice," a procedural SVG shell,
and a thermal receipt. The shell is born on screen as a scroll that unrolls along
its spiral arm, with a byōbu (folding-screen) battle drawn across it.

## What is genuinely strong

- **Two custom 1.5B LoRA adapters, both published and both used.** Voice
  (500 pairs, loss 0.89) and extraction (167 pairs, loss 0.81). The extraction
  LoRA replaced a prompted Qwen-7B, bringing the primary pipeline to ~2.6B active
  params (Whisper 809M + one 1.5B base serving both adapters on a single T4).
- **The groundedness eval is real and published with its raw data.** On 25
  held-out transcripts the fine-tuned 1.5B reaches semantic groundedness 0.76 vs
  the 7B's 0.72, at a third the active size, by paraphrasing rather than copying.
- **The shell is fully procedural and traceable.** Every visual element derives
  from a real session feature: dead ends are knots/fallen warriors, gotchas are
  jewels/archers, the breakthrough is the aperture/dragon, sentiment is the color
  arc. No image generation.
- **The SKILL.md is built for real uplift**, gotchas-first (symptom→cause→fix),
  "what does NOT work and why," transferable principles. Built and de-leaked
  deterministically from the structured extraction, not trusted to model prose.
- **Trace input works.** A real Claude Code or Codex session log runs through the
  same pipeline as audio. Judges can feed their own logs.
- **Graceful degradation is real and now observable.** If the extract adapter
  emits invalid JSON, the 7B fallback catches it. If the voice adapter is down, a
  deterministic extraction-based voice net prevents placeholder recaps. Every
  voice-path outcome is logged with a `[VOICE]` tag (EXTRACT_DOWN / VOICE_DOWN /
  VOICE_EMPTY / VOICE_OK / FALLBACK_VOICE_OK / NET_FROM_EXTRACTION / …) so failures
  are diagnosable, not mysterious.

## What is partial or has real caveats

- **Extraction parse reliability: 21/25 vs the 7B's 24/25.** The smaller model
  produces invalid JSON more often. In the app a brace-walking parser and field
  validators recover most of this, and the 7B fallback catches the rest, but the
  raw rate is a real cost of going small, and we report it unsoftened. (You will
  see `[VOICE] EXTRACT_DOWN` in the logs when this fires; the fallback then runs.)
- **The groundedness metric is calibrated to 5/6, not 6/6.** A hand-labeled
  calibration block (run before scoring, printed in the logs) missed one case:
  a grounded paraphrase scored just under threshold. The miss understates the
  LoRA rather than inflating it. 25 transcripts is a small sample; treat the
  LoRA-vs-7B gap as "matches or slightly exceeds," not "beats."
- **SKILL.md quality depends on extraction quality.** A good session yields
  transferable gotchas; a thin session yields thinner ones. An optional one-shot
  enrichment pass expands terse gotchas, gated by env and best-effort. We caught
  and fixed a real bug where few-shot examples in the enrichment prompt leaked
  into output (a game-theory skill got tree-coloring gotchas); the prompts are
  de-leaked and a guard now rejects any leaked phrasing.
- **The scroll-unroll animation ships ~1.7MB per shell** (14 stacked growth
  stages, so the parchment lays down ALONG the spiral arm rather than as a radial
  wipe). Browser-rendered via SMIL in a sandboxed iframe, with a "watch it unroll
  again" replay. On a slow connection the first paint takes a beat. If SMIL fails,
  the full shell still shows (nothing is hard-hidden); animation is enhancement,
  not a dependency.
- **The 3D paper curl rides the spiral tip via animateMotion.** Verified
  frame-by-frame in offline renders (cairosvg + headless Chromium). Exact
  tip-tracking in every browser is the part most likely to need a small tweak.

## What was freshly added near the deadline (use with that in mind)

- **Shared terrarium gallery.** Kept shells save to a Modal Volume; a grid shows
  all of them newest-first; each has a complete clickable permalink that re-loads
  and re-animates that shell. Freshly built and lightly tested. Honest caveats:
  each grid card is its own iframe, so past ~30-40 shells the grid gets heavy
  (lazy-loading is the fix, not yet done). Gallery saves depend on the Modal
  endpoint URLs matching the client; if they drift, a save fails and the UI says
  so rather than failing silently.
- **Battle Trace (experimental).** A temporal replay of the same session as a war
  between you (the Agent) and the Environment, fed by the SAME extraction (no
  second parser, no OTel). Framed as complementary to the shell: the shell is the
  slug's *memory* of how the battle ended (the frozen folding screen); the trace
  is the *replay* of it in time. It is Canvas-2D with simple figurative
  combatants (a samurai general, a horned adversary, fallen warriors, a dragon at
  the breakthrough). Honest about its level: these are clean vector figures, not
  game-quality sprite art. Labeled "experimental" in the UI.

## What is aspirational / not built

- **Session diff view** (compare two sessions' shells) is not built.
- **Closing the parse-rate gap** needs more training pairs and constrained
  decoding; not done.
- **Higher-fidelity Battle Trace art** (detailed sprite-grade samurai) is not
  built; the current figures are deliberately simple vector shapes (see the
  Battle Trace note above).

## Infrastructure honesty

- The Qwen-7B still exists in the codebase but ONLY as a labeled fallback when the
  Modal extract path returns nothing usable (including the invalid-JSON case
  above). The primary path is the 1.5B dual adapter. The README architecture table
  reflects this.
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
- Failure handling: the Space logs tag every voice-path outcome with `[VOICE]`.

## The one-sentence honest summary

A small, slow, genuinely ~2.6B pipeline that turns a coding session into a
transferable skill, a grounded recap, and a procedural shell, measured honestly
(including where the small model costs us), with graceful, observable degradation,
and every model and the eval data published for anyone to check.
