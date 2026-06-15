---
title: TurboSkillSlug
emoji: 🐌
colorFrom: purple
colorTo: yellow
sdk: gradio
sdk_version: "6.16.0"
python_version: "3.12"
app_file: app.py
pinned: false
short_description: Turn a coding session into a skill, recap, and shell.
tags:
  - hackathon
  - build-small-hackathon
  - thousand-token-wood
  - codex
  - best-demo
  - off-brand
  - well-tuned
  - tiny-titan
models:
  - legendarydragontamer/slugvoice-qwen2.5-1.5b-lora
  - legendarydragontamer/slugextract-qwen2.5-1.5b-lora
  - Qwen/Qwen2.5-1.5B-Instruct
  - openai/whisper-large-v3-turbo
datasets:
  - legendarydragontamer/turboskillslug-groundedness-eval
---

# TurboSkillSlug

**Feed it a coding session. Get back a reusable SKILL.md, a grounded spoken
recap, and a procedural shell that encodes the whole session as art.**

The session goes in one of two ways: narrate it aloud, or drop a real Claude Code
or Codex CLI session log (`.jsonl`). A fine-tuned 1.5B model extracts what you
tried, what failed, and what finally worked. Total active pipeline: **~2.6B
parameters**, measured to match a 7B on groundedness at a third the size.

Then the slug gives you four things:

1. **A SKILL.md** another LLM can actually use: the non-obvious gotchas
   (symptom → cause → fix), the approaches that fail and why, the breakthrough.
   Built to give a frontier model real uplift, not a session summary.
2. **A spoken recap** in a fine-tuned "slug voice," every line grounded in
   something that happened, never reciting invented numbers.
3. **A shell** whose spiral, knots, jewels, and colors all derive from your
   session, born on screen as a scroll that unrolls along its own arm, with a
   byōbu-style battle inked across it (dead ends are fallen warriors, the
   breakthrough is a dragon).
4. **A receipt** like a thermal printout: approaches tried, dead ends, mood.

### The slug witnesses every kind of session, not just debugging

Most coding sessions are not bug hunts. They are exploring an unfamiliar repo,
writing docs, setting up tooling, building a feature. A witness that only has
eyes for "what broke and what fixed it" leaves those sessions with a hollow
shell.

So the slug detects the session's genre (debugging, exploration, authoring,
feature, refactor, setup) and witnesses the right thing for each:

- debugging → the struggle: dead ends and the breakthrough
- exploration → the discoveries: the non-obvious facts learned about the codebase
- authoring → the decisions, and the false assumptions caught before they became wrong docs
- feature / refactor / setup → what was built or changed, and what would break if done naively

The shell's vocabulary adapts with it: for an exploration session the rim jewels
are discoveries, the aperture is the clearest insight. Genre detection is pure
pattern-matching: no model call, no added latency.

Why this matters concretely: on a real exploration trace, the slug surfaced that
a project's checkpoint mirror uses a custom git ref namespace
(`refs/entire/...`) that a standard `git fetch --all` will miss. That is exactly
the kind of private, non-derivable knowledge a SKILL.md exists to carry, and it
came from a session that had no "bug" at all.

Every shell is unique because every session is unique.

## Try it in one click

Two tabs, two sample inputs:

- **narrate aloud** — a sample build session (audio)
- **drop a session trace** — a sample Claude Code `.jsonl` trace

Or bring your own: upload a recording, or drag a real session log from
`~/.claude/projects/.../*.jsonl` or `~/.codex/sessions/.../*.jsonl`. Judges can
feed their own agent logs and watch the slug read them.

## Demo

Watch the demo: **[youtu.be/qSP9olWRv7o](https://youtu.be/qSP9olWRv7o)**

## Social

The launch post: **[x.com/anubhav27071997](https://x.com/anubhav27071997/status/2063970171010826540)**

## Why this is hard the right way

The slug's entire promise is a witness that only says what it saw. That makes
**groundedness** the core engineering problem: a small model that invents facts
is worthless here. So we measured it, honestly, and published the data.

### Groundedness: does the small model hallucinate more than the 7B it replaced?

On 25 held-out transcripts, comparing the shipped fine-tuned 1.5B against the
Qwen-7B it replaced and its own un-tuned 1.5B base:

| system | semantic groundedness | lexical | parse | facts |
|---|---:|---:|---:|---:|
| prompted 7B | 0.716 | 0.576 | 24/25 | 272 |
| prompted 1.5B base | 0.565 | 0.390 | 21/25 | 140 |
| **fine-tuned 1.5B LoRA** | **0.762** | 0.378 | 21/25 | 195 |

The fine-tuned 1.5B **matches and slightly exceeds the 7B (0.76 vs 0.72) at a
third of the active size.** It does this by paraphrasing rather than copying:
lowest lexical overlap, highest semantic groundedness, the signature of a model
that restates meaning instead of echoing words.

Reported with its costs, not spun: the LoRA produces valid JSON less often
(21/25 vs 24/25), and the semantic metric passed 5/6 hand-labeled calibration
cases (the one miss understates the LoRA, not the reverse). 25 transcripts is a
small sample, so the honest claim is "matches or slightly exceeds," not "beats."
Raw generations and per-fact scores are published so anyone can re-score:
[turboskillslug-groundedness-eval](https://huggingface.co/datasets/legendarydragontamer/turboskillslug-groundedness-eval).

## The SKILL.md is the real gift

A skill file is only worth shipping if it helps an LLM that is already capable
without it. A summary does not. So the SKILL.md is built to carry the
**non-obvious, transferable** knowledge a frontier model cannot derive on its own:

- **Gotchas as symptom → cause → fix**, not labels. "Processing leaf nodes first
  looks natural but breaks because a parent depends on its children being
  finalized; process deepest-first" — not "ordering unclear."
- **What does NOT work, and why**, so the model skips the dead ends you already
  paid for.
- **Transferable principles** distilled from the arc, not a diary of the session.
- **A negative guardrail under each gotcha**, phrased as a "do not X / verify Y
  before assuming" rule. This follows the 2026 RuleShaping finding that negative,
  state-dependent guardrails are the rule type that actually helps a model, and
  it is generated deterministically with no model call.

Terse gotchas are expanded by an optional one-shot pass, guarded so example
phrasing can never leak into output.

## How the shell reads your session

| What happened | How the shell shows it |
|---|---|
| Duration | Overall size and number of spiral turns |
| Each approach tried | Spiral arm density |
| Each dead end | A dark knot — and a fallen warrior in the battle layer |
| The breakthrough | The glowing aperture at the tip — and a dragon |
| Gotchas | Iridescent jewels along the rim — and archers |
| Your emotional arc | Color gradient from start to end |

A frustrated session ending in relief is red-to-green. A curious exploration
ending in delight is warm gold. A long grind is cold blue-grey. The color story
is the emotional story.

Procedural SVG: nacre texture filters, HSL color harmonies, bezier-smoothed
curves. **No diffusion, no image generation.** Every pixel traces to a real
session feature, which is the whole point: if a diffusion model drew the shell,
"this knot is your dead end" would stop being true. The shell is born as a scroll
unrolling along its spiral arm, led by a 3D paper curl, with the byōbu battle
inking on as the parchment is laid. There is a "watch it unroll again" replay.

Kept shells go into a **shared terrarium** (gallery): a living collection where
every shell is the fingerprint of a real session, each with a `?shell=<id>`
permalink.

## Architecture

The full primary pipeline runs on Modal at **~2.6B active parameters**. The
Qwen-7B is a labeled fallback only, not on the primary path.

| Component | Model | Params | Infrastructure |
|---|---|---|---|
| Transcription | `openai/whisper-large-v3-turbo` | 809M | Modal T4 |
| Feature extraction | `slugextract-qwen2.5-1.5b-lora` | 1.5B | Modal T4 (shared) |
| Slug voice | `slugvoice-qwen2.5-1.5b-lora` | 1.5B | Modal T4 (shared) |
| Spoken recap | Chatterbox TTS | ~300M | Modal A10G |
| Genre detection | Pattern matching (no model) | 0 | CPU |
| Shell + Receipt | Procedural SVG (no model) | 0 | CPU |
| Extraction fallback | `Qwen/Qwen2.5-7B-Instruct` | 7B | HF Inference (fallback only) |

**Two custom LoRA adapters, one base model, one T4.** Both adapters are
fine-tunes of Qwen2.5-1.5B-Instruct, loaded onto a single base on a single T4 and
switched per request, so the whole language pipeline runs on one GPU.

- **SlugVoice** ([adapter](https://huggingface.co/legendarydragontamer/slugvoice-qwen2.5-1.5b-lora)):
  500 hand-crafted (transcript snippet, slug observation) pairs. Loss 4.97 → 0.89.
- **SlugExtract** ([adapter](https://huggingface.co/legendarydragontamer/slugextract-qwen2.5-1.5b-lora)):
  167 balanced (transcript, structured-JSON) pairs across 14 sentiment arcs.
  Loss 1.88 → 0.81. Replaces the Qwen-7B extractor; brings the pipeline to ~2.6B.

## How Modal is used

1. **Fine-tuning.** Both LoRAs trained on Modal (A10G). SlugExtract on a pure
   transformers + PEFT + bitsandbytes stack.
2. **Serving.** Whisper on a T4; both LoRAs on a single shared T4 via PEFT
   multi-adapter, switched per request. Kept-warm containers (one always-on plus
   a buffer) for demo reliability.
3. **TTS.** Chatterbox on an A10G speaks the recap.
4. **Evaluation.** The groundedness eval (three models, 25 transcripts, two
   metrics) runs as a Modal job, persisting raw generations to a Volume.
5. **Gallery.** The shared terrarium's save/list/fetch endpoints run on Modal,
   backed by the same Volume.

If the primary extraction misses, the app retries on the same small model and
otherwise degrades to a clear message, so it never crashes mid-render.

## Built with OpenAI Codex

Built using [OpenAI Codex](https://openai.com/codex) as the primary coding agent.
Full commit history:
**[github.com/AnubhavBharadwaaj/turbo-skill-slug](https://github.com/AnubhavBharadwaaj/turbo-skill-slug)**

Codex handled scaffolding, the Gradio skeleton, the shell SVG geometry, tests,
dependency wiring, and deployment fixes. Human judgment went into the slug's
voice, the shell's visual design, the grounding constraints, and the two LoRA
fine-tunes.

## Technical choices and why

**Procedural SVG over generated images.** Every element traces to a real feature;
a diffusion model would break that link.

**Fine-tuned 1.5B over prompted 7B for both voice and extraction.** A prompted
large model copies examples; a fine-tuned small model learns the pattern. The
eval shows the extraction fine-tune reaching 7B-level groundedness at a third the
size.

**Counts live on the receipt, never in the voice.** The voice is forbidden from
reciting tallies, so it can never state a number that contradicts the record. The
slug describes moments; the receipt does arithmetic.

**Graceful degradation everywhere.** If the primary Modal extraction misses, the
app retries once on the same small model, then shows a clear "try again" message
rather than crashing. Unexpected sentiment → closest valid label. Animation fails
→ the full shell still shows (nothing is hard-hidden). Nothing crashes on edge
cases.

## Hackathon patches

| Patch | Status | Evidence |
|---|---|---|
| 🍄 Thousand Token Wood | ✅ | A slug grows a shell from your session |
| 🏆 Best Use of Codex | ✅ | Codex-attributed commits, documented usage, public repo |
| 🎬 Best Demo | ✅ | [Demo video](https://youtu.be/qSP9olWRv7o) + two one-click samples |
| 🎨 Off Brand | ✅ | Procedural shell: scroll-unroll birth, byōbu battle layer, thermal receipt |
| 🎯 Well-Tuned | ✅ | TWO published LoRAs + a published, re-scorable groundedness eval |
| 🔬 Tiny Titan | ✅ | ~2.6B primary pipeline (Whisper 809M + 1.5B). 7B is fallback only. |
| 🏗️ Best Use of Modal | ✅ | Two fine-tunes, dual-adapter serving, TTS, eval, and gallery on Modal |
| 📓 Field Notes | ✅ | [Blog article](https://huggingface.co/blog/build-small-hackathon/turboskillslug-shell-from-session) |

## Honesty

Full caveats (parse-rate cost, the eval's 5/6 calibration, the animation
payload, what is freshly built) are documented in
[HONEST_SUBMISSION.md](https://github.com/AnubhavBharadwaaj/turbo-skill-slug/blob/main/HONEST_SUBMISSION.md).
Every model and the eval data are published for anyone to verify.

## Research foundation: from one skill to lifecycle-governed rules

Beyond the shipped app, this project carries an offline-validated research layer
that answers a sharper question than "can a small model extract a skill": *when
does an extracted artifact actually help a capable model, and how should many
sessions compound into durable knowledge?*

This work is validated offline (it is not yet wired into the live Space) and is
documented and tested in the repo. Stated plainly so the line between shipped and
researched is clear:

- **When skills help (measured).** A blind, calibrated eval (one model answers,
  an independent model judges) found that a generated skill gives a frontier
  model uplift *only* when it carries knowledge that could not be in training
  data: private behavior, post-cutoff facts, project conventions. General
  algorithmic skills gave 0.0 uplift; novel/private ones gave real uplift. The
  dividing line is provenance, not difficulty.

- **Compounding across sessions (built, offline-tested).** A promotion engine,
  grounded in the 2026 "Experience Compression Spectrum" framing, consolidates
  gotchas that recur across multiple sessions of the same codebase into compact,
  guardrail-phrased rules, with provenance, confidence, and a validation gate
  that demotes rules that stop holding. Rule phrasing follows the "RuleShaping"
  finding that negative, state-dependent guardrails help where positive
  directives hurt.

- **Faithful trace distillation (built, offline-tested).** A from-scratch
  implementation of the 2026 "Trace2Skill" method (validation-gated error
  analysis, hierarchical prevalent-pattern merging, niche items routed to
  references) for higher-fidelity extraction.

An honest result from running the extractor on real public agent traces: its
gotchas are specific and real (it named exact functions, ref namespaces, and
build-tool quirks), but cross-session promotion only fires within a single
codebase, because two different repos never share the same private trap. That is
a true property of the problem, reported rather than hidden.

Full method, code, and tests live in the repo; the research is a foundation for
where the slug goes next, not a claim about the current Space.

## What comes next

1. **Session diff view.** Upload two sessions, see how the shells differ.
2. **Tighter extraction reliability.** Close the parse-rate gap (21/25 vs the
   7B's 24/25) with more training pairs and constrained decoding.

## Links

- **Space:** [build-small-hackathon/TurboSkillSlug](https://huggingface.co/spaces/build-small-hackathon/TurboSkillSlug)
- **Code:** [github.com/AnubhavBharadwaaj/turbo-skill-slug](https://github.com/AnubhavBharadwaaj/turbo-skill-slug)
- **SlugVoice LoRA:** [slugvoice-qwen2.5-1.5b-lora](https://huggingface.co/legendarydragontamer/slugvoice-qwen2.5-1.5b-lora)
- **SlugExtract LoRA:** [slugextract-qwen2.5-1.5b-lora](https://huggingface.co/legendarydragontamer/slugextract-qwen2.5-1.5b-lora)
- **Groundedness eval:** [turboskillslug-groundedness-eval](https://huggingface.co/datasets/legendarydragontamer/turboskillslug-groundedness-eval)
- **Demo:** [youtu.be/qSP9olWRv7o](https://youtu.be/qSP9olWRv7o)
- **Social post:** [x.com/anubhav27071997](https://x.com/anubhav27071997/status/2063970171010826540)
- **Blog:** [turboskillslug-shell-from-session](https://huggingface.co/blog/build-small-hackathon/turboskillslug-shell-from-session)

---

*The slug watches, gives its gifts, and goes back to sleep.*
*I was here.*
