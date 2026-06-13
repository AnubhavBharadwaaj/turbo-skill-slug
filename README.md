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
short_description: A small slow companion who watches you build.
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

*A small, slow companion who sits beside you while you build.*

Give the slug a build session two ways: **narrate it aloud** (upload a recording
of what you tried, what failed, what finally worked), or **drop an agent session
trace** (a Claude Code or Codex CLI `.jsonl` log of your actual work). The slug
sits quietly through it, then gives you four gifts:

1. **A slug recap** in its own fine-tuned voice, each observation grounded in
   something that actually happened, and never reciting invented counts
2. **A SKILL.md** with the structured record: what you tried, why it failed, the
   breakthrough, the gotchas
3. **A shell** whose spiral, knots, jewels, and colors all derive from the shape
   of your work
4. **A receipt** like a thermal printout of your session: approaches tried, dead
   ends counted, mood tracked

Every shell is unique because every build session is unique.

## Try it

Two tabs, two sample inputs, each one click:

- **narrate aloud** — a sample build session (audio)
- **drop a session trace** — a sample Claude Code `.jsonl` trace

Or bring your own: upload a recording, or drag a real session log from
`~/.claude/projects/.../*.jsonl` or `~/.codex/sessions/.../*.jsonl`.

## Demo

Watch the full demo: [youtu.be/jvVtbkjd8cw](https://youtu.be/jvVtbkjd8cw)

*(The demo shows the audio flow; the agent-trace input shipped after recording
and is live in the Space now.)*

## How the shell reads your session

| What happened in your session | How the shell shows it |
|---|---|
| Duration | Overall size and number of spiral turns |
| Each approach you tried | Spiral arm density |
| Each dead end | A dark knot on the spiral body |
| The breakthrough moment | The glowing aperture at the spiral's tip |
| Gotchas you hit | Iridescent jewels along the outer rim |
| Your emotional arc | Color gradient from start to end |

A frustrated session that ends in relief produces red-to-green gradients. A
curious exploration that ends in delight produces warm gold. A long exhausting
grind produces cold blue-grey. The color story is the emotional story.

The shell uses procedural SVG with nacre (mother of pearl) texture filters, HSL
derived color harmonies, and bezier smoothed curves. No diffusion models, no
image generation. Math that looks like art.

## The receipt

Alongside the shell, you get a thermal-receipt-style SVG that lists every
approach and whether it failed or succeeded, dead end / gotcha / breakthrough
counts, your mood going in and coming out, and a barcode generated from your
session data. The receipt is the practical artifact. The shell is the emotional
one. The counts on both are computed directly from the extraction, so they are
always consistent with what the slug witnessed.

## Architecture

The full primary pipeline runs on Modal and is **~2.6B active parameters**. The
Qwen-7B is retained only as a labeled fallback when a Modal endpoint is briefly
unavailable; it is not on the primary path.

| Component | Model | Params | Infrastructure |
|---|---|---|---|
| Transcription | `openai/whisper-large-v3-turbo` | 809M | Modal T4 |
| Feature extraction | `slugextract-qwen2.5-1.5b-lora` | 1.5B | Modal T4 (shared) |
| Slug voice | `slugvoice-qwen2.5-1.5b-lora` | 1.5B | Modal T4 (shared) |
| Spoken recap | Chatterbox TTS | ~300M | Modal A10G |
| Shell + Receipt | Procedural SVG (no model) | 0 | CPU |
| Extraction fallback | `Qwen/Qwen2.5-7B-Instruct` | 7B | HF Inference (fallback only) |

**Two custom LoRA adapters, one base model, one T4.** The extraction adapter and
the voice adapter are both fine-tunes of Qwen2.5-1.5B-Instruct. They are loaded
onto a single base model on a single T4 and switched per request, so the whole
language pipeline (extract the structured record, then speak the recap) runs on
one GPU.

### The two adapters

- **SlugVoice** ([slugvoice-qwen2.5-1.5b-lora](https://huggingface.co/legendarydragontamer/slugvoice-qwen2.5-1.5b-lora)):
  500 hand-crafted (transcript snippet, slug observation) pairs. Loss 4.97 → 0.89.
  Teaches the voice: short, specific, grounded, second-person.
- **SlugExtract** ([slugextract-qwen2.5-1.5b-lora](https://huggingface.co/legendarydragontamer/slugextract-qwen2.5-1.5b-lora)):
  167 balanced (transcript, structured-JSON) pairs, every example with a non-empty
  dead-ends list, spanning 14 sentiment arcs. Loss 1.88 → 0.81. Replaces the
  Qwen-7B feature extractor and brings the whole pipeline under ~2.6B.

## Groundedness: does the small model hallucinate more?

The slug's entire promise is a witness that only says what it saw, so the
extraction model's first duty is not to invent facts. We measured this on 25
held-out transcripts, comparing the shipped 1.5B LoRA against the Qwen-7B it
replaced and against its own un-tuned 1.5B base.

| system | semantic groundedness | lexical | parse | facts |
|---|---:|---:|---:|---:|
| prompted 7B | 0.716 | 0.576 | 24/25 | 272 |
| prompted 1.5B base | 0.565 | 0.390 | 21/25 | 140 |
| **fine-tuned 1.5B LoRA** | **0.762** | 0.378 | 21/25 | 195 |

Under embedding-based semantic groundedness, the fine-tuned 1.5B **matches and
slightly exceeds the 7B (0.76 vs 0.72) at a third of the active size.** It does
this by paraphrasing rather than copying: it has the lowest lexical overlap but
the highest semantic groundedness, the signature of a model that restates
meaning instead of echoing words.

We report this honestly, including the costs: the LoRA produces valid JSON less
often than the 7B (21/25 vs 24/25), and the semantic metric's threshold passed
5/6 hand-labeled calibration cases (the one miss was a grounded fact scored too
strictly, so it understates rather than inflates the LoRA). Raw generations and
per-fact scores are published so anyone can re-score:
[turboskillslug-groundedness-eval](https://huggingface.co/datasets/legendarydragontamer/turboskillslug-groundedness-eval).

The slug's spoken recap is additionally guarded so it never recites event
tallies (it describes specific moments, not counts), which removes the most
visible way a small model can contradict the record it just produced.

## How Modal is used

1. **Fine-tuning.** Both LoRAs were trained on Modal. SlugVoice on an A10G
   (500 pairs, 5 epochs, ~$1.50). SlugExtract on an A10G with a pure
   transformers + PEFT + bitsandbytes stack (167 pairs, 4 epochs, loss 0.81).
2. **Serving.** Whisper on a T4; both LoRAs on a single shared T4 via PEFT
   multi-adapter, switched per request. The dual-adapter server can hold one warm
   container for demo reliability or scale to zero when idle.
3. **TTS.** Chatterbox on an A10G converts the written recap to speech.
4. **Evaluation.** The groundedness eval (three models, 25 transcripts, two
   metrics) runs as a Modal A10G job, persisting raw generations and scores to a
   Modal Volume.

The app on HF Spaces calls these endpoints over HTTP. If a Modal endpoint is
briefly unavailable, the app falls back gracefully (extraction to the Qwen-7B on
HF Inference; everything still returns a result).

## Built with OpenAI Codex

This project was built using [OpenAI Codex](https://openai.com/codex) as the
primary coding agent. Full commit history:
**[github.com/AnubhavBharadwaaj/turbo-skill-slug](https://github.com/AnubhavBharadwaaj/turbo-skill-slug)**

Codex handled scaffolding, the Gradio app skeleton, the shell SVG geometry,
tests, dependency wiring, and the deployment fixes (Gradio version
compatibility, provider routing, audio content-type handling). Human judgment
went into the slug's voice (the hand-written seed utterances that define the
tone), the shell's visual design, the extraction prompt's grounding
constraints, and the two LoRA fine-tunes.

## Technical choices and why

**Procedural SVG over generated images.** Every visual element traces back to a
real session feature. A diffusion model would break the link between "this knot
is your dead end" and the data. The visual meaning has to be deterministic.

**Fine-tuned 1.5B over prompted 7B for BOTH voice and extraction.** A prompted
large model copies examples; a fine-tuned small model learns the pattern. The
groundedness eval above shows the extraction fine-tune reaching 7B-level
semantic faithfulness at a third the size.

**Counts live on the receipt, never in the slug's voice.** The shell and receipt
compute dead-end / gotcha / breakthrough counts directly from the extraction.
The voice is forbidden from reciting tallies, so it can never state a number that
contradicts the record. The slug describes moments; the receipt does arithmetic.

**Duration reconciliation.** For audio, the app takes the larger of the measured
file length and the model's described-duration estimate, so a three-hour session
narrated in four minutes still grows a three-hour shell. For traces, it trusts
the model's estimate.

**Graceful fallback everywhere.** Cold Modal endpoint → HF Inference fallback.
Unexpected sentiment value → mapped to the closest valid label. Fewer than 5
voice lines after guarding → padded. Nothing crashes on edge cases.

## Hackathon patches

| Patch | Status | Evidence |
|---|---|---|
| 🍄 Thousand Token Wood | ✅ | Whimsical shell grows from your session |
| 🏆 Best Use of Codex | ✅ | Codex-attributed commits, documented usage, public GitHub repo |
| 🎬 Best Demo | ✅ | [Demo video](https://youtu.be/jvVtbkjd8cw) + social post + two one-click samples |
| 🎨 Off Brand | ✅ | Custom SVG shell with nacre texture + thermal receipt artifact |
| 🎯 Well-Tuned | ✅ | TWO custom LoRAs published: [voice](https://huggingface.co/legendarydragontamer/slugvoice-qwen2.5-1.5b-lora) + [extract](https://huggingface.co/legendarydragontamer/slugextract-qwen2.5-1.5b-lora), with a published groundedness eval |
| 🔬 Tiny Titan | ✅ | Primary pipeline ~2.6B (Whisper 809M + 1.5B extraction/voice). 7B is fallback only. |
| 🏗️ Best Use of Modal | ✅ | Two fine-tunes, dual-adapter serving on one T4, TTS, and the eval all on Modal |
| 📓 Field Notes | ✅ | [Blog article](https://huggingface.co/blog/build-small-hackathon/turboskillslug-shell-from-session) |

## What comes next

1. **Terrarium frontend.** A progressive shell reveal that grows as the session
   is processed, with a shared shell gallery of session fingerprints.
2. **Session diff view.** Upload two sessions, see how the shells differ, track
   growth over time.
3. **Tighter extraction reliability.** Close the parse-rate gap (currently
   21/25 vs the 7B's 24/25) with more training pairs and constrained decoding.

## Shipped recently

- **Agent session trace input.** Claude Code and Codex CLI `.jsonl` logs run
  through the same pipeline as audio. The slug watches your AI collaboration.
- **Extraction fine-tune.** A second 1.5B LoRA replaced the Qwen-7B extractor,
  bringing the primary pipeline under ~2.6B.
- **Groundedness eval.** Three models, 25 held-out transcripts, two metrics,
  published with raw data.

## Social

[Twitter/X post](https://x.com/anubhav27071997/status/2063970171010826540?s=20)

## Links

- **Space:** [build-small-hackathon/TurboSkillSlug](https://huggingface.co/spaces/build-small-hackathon/TurboSkillSlug)
- **Code:** [github.com/AnubhavBharadwaaj/turbo-skill-slug](https://github.com/AnubhavBharadwaaj/turbo-skill-slug)
- **SlugVoice LoRA:** [slugvoice-qwen2.5-1.5b-lora](https://huggingface.co/legendarydragontamer/slugvoice-qwen2.5-1.5b-lora)
- **SlugExtract LoRA:** [slugextract-qwen2.5-1.5b-lora](https://huggingface.co/legendarydragontamer/slugextract-qwen2.5-1.5b-lora)
- **Groundedness eval:** [turboskillslug-groundedness-eval](https://huggingface.co/datasets/legendarydragontamer/turboskillslug-groundedness-eval)
- **Demo:** [youtu.be/jvVtbkjd8cw](https://youtu.be/jvVtbkjd8cw)
- **Blog:** [turboskillslug-shell-from-session](https://huggingface.co/blog/build-small-hackathon/turboskillslug-shell-from-session)

---

*The slug watches, gives its gifts, and goes back to sleep.*
*I was here.*
