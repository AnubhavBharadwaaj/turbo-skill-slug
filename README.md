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
  - Qwen/Qwen2.5-1.5B-Instruct
  - openai/whisper-large-v3-turbo
---

# TurboSkillSlug

*A small, slow companion who sits beside you while you build.*

Upload a recording of your build session. You narrating what you are trying, what is failing, what finally works. The slug will sit quietly through it, then give you four gifts:

1. **A slug recap** in their own fine-tuned voice, each observation grounded in something that actually happened
2. **A SKILL.md** with the structured record of your session: what you tried, why it failed, the breakthrough, the gotchas
3. **A shell** whose spiral, knots, jewels, and colors are all derived from the shape of your work
4. **A receipt** that looks like a thermal printout of your session: approaches tried, dead ends counted, mood tracked

Every shell is unique because every build session is unique.

## Try it

There is a sample session you can try with one click. Or upload your own recording and watch the slug grow a shell from your work.

## Demo

Watch the full demo: [youtu.be/jvVtbkjd8cw](https://youtu.be/jvVtbkjd8cw)

## How the shell reads your session

| What happened in your session | How the shell shows it |
|---|---|
| Duration | Overall size and number of spiral turns |
| Each approach you tried | Spiral arm density |
| Each dead end | A dark knot on the spiral body |
| The breakthrough moment | The glowing aperture at the spiral's tip |
| Gotchas you hit | Iridescent jewels along the outer rim |
| Your emotional arc | Color gradient from start to end |

A frustrated session that ends in relief produces a shell with red-to-green gradients. A curious exploration that ends in delight produces warm gold. A long exhausting grind produces cold blue-grey. The color story is the emotional story.

The shell uses procedural SVG with nacre (mother of pearl) texture filters, HSL derived color harmonies, and bezier smoothed curves. No diffusion models, no image generation. Math that looks like art.

## The receipt

Alongside the shell, you get a thermal-receipt-style SVG that lists:
- Every approach you tried and whether it failed or succeeded
- Dead end count, gotcha count, breakthrough position
- Your mood going in and coming out
- A unique barcode generated from your session data

The receipt is the practical artifact. The shell is the emotional one.

## Architecture

TurboSkillSlug runs on three Modal endpoints and one HF Inference API call:

| Component | Model | Params | Infrastructure |
|---|---|---|---|
| Transcription | `openai/whisper-large-v3-turbo` | 809M | Modal T4 |
| Feature extraction | `Qwen/Qwen2.5-7B-Instruct` | 7B | HF Inference API |
| Slug voice | `legendarydragontamer/slugvoice-qwen2.5-1.5b-lora` | 1.5B | Modal T4 |
| Spoken recap | Chatterbox TTS | ~300M | Modal A10G |
| Shell + Receipt | Procedural SVG (no model) | 0 | CPU |

The slug voice is a LoRA fine-tune of Qwen2.5-1.5B-Instruct, trained on 500 hand-crafted (transcript snippet, slug observation) pairs using Unsloth on a Modal A10G. Training took 3 minutes 39 seconds. Loss dropped from 4.97 to 0.89. The adapter is published on the Hub: [legendarydragontamer/slugvoice-qwen2.5-1.5b-lora](https://huggingface.co/legendarydragontamer/slugvoice-qwen2.5-1.5b-lora).

## How Modal is used

Modal powers three parts of the pipeline:

1. **Fine-tuning.** The SlugVoice LoRA was trained on Modal using an A10G GPU with Unsloth for 2x faster training. 500 training pairs, 5 epochs, 160 steps, $1.50 in compute.

2. **Serving.** The fine-tuned SlugVoice model and Whisper are each served as Modal web endpoints on T4 GPUs. They scale to zero when idle and cold-start on demand. No cost when nobody is using the app.

3. **TTS.** Chatterbox TTS runs on a Modal A10G to convert the slug's written recap into spoken audio. The slug literally speaks its observations aloud.

The app on HF Spaces calls these Modal endpoints over HTTP. If any Modal endpoint is unavailable (cold start, timeout), the app falls back gracefully to HF Inference API.

## Built with OpenAI Codex

This project was built using [OpenAI Codex](https://openai.com/codex) as the primary coding agent. The full commit history is in the public GitHub repo:

**[github.com/AnubhavBharadwaaj/turbo-skill-slug](https://github.com/AnubhavBharadwaaj/turbo-skill-slug)**

### How Codex built this

Codex was given one task at a time, each scoped as a single pull request:

- **PR #1: Scaffold.** Codex created the Gradio app skeleton, requirements, HF Space YAML, .gitignore, and the first test. It seeded the main branch and opened the PR with clean attribution.
- **PR #2: Shell SVG generator.** Codex took a reference implementation of the logarithmic spiral geometry, productionized it with type hints and docstrings, wired it into the Gradio app with inline preview and downloadable files, and added the shell test. All four tests green before merge.
- **Subsequent commits** addressed deployment fixes (Gradio version compatibility, Inference API provider routing, audio content type handling) and extraction prompt tightening (constrained sentiment vocabulary, grounded slug voice, structured SKILL.md validation).

Every commit in the repo is attributed to Codex or to the builder responding to Codex's work.

### What Codex was good at

Scaffolding, test writing, dependency wiring, and mechanical refactoring. Codex handled the Gradio component plumbing and pytest mocking without hand-holding.

### What needed human judgment

The slug's voice (50 hand-written seed utterances that define the tone, expanded to 500 for the fine-tune), the shell's visual design (procedural SVG tuning for beauty, not just correctness), and the extraction prompt's grounding constraints (ensuring the slug never claims to witness something the transcript does not support).

## Technical choices and why

**Procedural SVG over generated images.** The whole point of the shell is that every visual element traces back to a real session feature. If a diffusion model generated the shell, the connection between "this knot is your dead end" breaks. The visual meaning has to be deterministic and traceable.

**Fine-tuned 1.5B over prompted 7B for slug voice.** A prompted 7B model copies example utterances verbatim. A fine-tuned 1.5B model trained on 500 diverse pairs learns the pattern (short, specific, grounded, second-person) without copying. The fine-tune solved a quality problem, not just a size problem.

**Audio duration from the file, not the model.** Qwen guesses session durations from transcript content ("thirty minutes of debugging" in a 90-second recording). The app measures the actual WAV duration and overrides the guess. The shell reflects what the slug actually heard.

**Graceful fallback everywhere.** If Modal is cold-starting, the app falls back to HF Inference. If sentiment extraction produces an unexpected value, the validator maps it to the closest valid label instead of crashing. If the slug produces fewer than 5 lines, the app pads instead of erroring. Nothing crashes on edge cases.

## What surprised me

The slug voice is the hardest part and it is not an engineering problem. It is a writing problem. Getting a model to speak in a specific register (earnest, quiet, concrete, never cute) requires defining that register through hundreds of hand-written examples. The fine-tune did not replace the writing. It scaled it.

The shell quality depends almost entirely on extraction quality. Two sessions that produce the same sentiment arc generate similar-looking shells. Making the extraction honest (a quick easy session should end "joyful" not "resolved", a grinding marathon should end "exhausted" not "resolved") is what makes the shells visually distinct.

## Hackathon patches

| Patch | Status | Evidence |
|---|---|---|
| 🍄 Thousand Token Wood | ✅ | Whimsical shell grows from your session |
| 🏆 Best Use of Codex | ✅ | Codex-attributed commits, documented usage, public GitHub repo |
| 🎬 Best Demo | ✅ | [Demo video](https://youtu.be/jvVtbkjd8cw) + social post + working sample session |
| 🎨 Off Brand | ✅ | Custom SVG shell with nacre texture, thermal receipt artifact |
| 🎯 Well-Tuned | ✅ | Custom LoRA published: [slugvoice-qwen2.5-1.5b-lora](https://huggingface.co/legendarydragontamer/slugvoice-qwen2.5-1.5b-lora) |
| 🔬 Tiny Titan | ✅ | SlugVoice is 1.5B, Whisper is 809M. Total active inference: 2.3B |
| 🏗️ Best Use of Modal | ✅ | Fine-tune, serve, and TTS all on Modal |
| 📓 Field Notes | ✅ | [Blog article](https://huggingface.co/blog/build-small-hackathon/turboskillslug-shell-from-session) |

## What comes next

1. **Agent session logs as input.** Replace audio upload with Codex/Claude Code session traces. The slug watches your AI collaboration, not just your voice.
2. **Shell gallery.** A shared collection where builders post their shells. Each one is a fingerprint of a session.
3. **Extraction model fine-tune.** Train a small model for feature extraction too, removing the Qwen-7B dependency. Full pipeline under 4B.
4. **Session diff view.** Upload two sessions and see how your shells differ. Track your growth over time.

## Social

[Twitter/X post](https://x.com/anubhav27071997/status/2063970171010826540?s=20)

## Links

- **Space:** [build-small-hackathon/TurboSkillSlug](https://huggingface.co/spaces/build-small-hackathon/TurboSkillSlug)
- **Code:** [github.com/AnubhavBharadwaaj/turbo-skill-slug](https://github.com/AnubhavBharadwaaj/turbo-skill-slug)
- **LoRA:** [legendarydragontamer/slugvoice-qwen2.5-1.5b-lora](https://huggingface.co/legendarydragontamer/slugvoice-qwen2.5-1.5b-lora)
- **Demo:** [youtu.be/jvVtbkjd8cw](https://youtu.be/jvVtbkjd8cw)
- **Blog:** [turboskillslug-shell-from-session](https://huggingface.co/blog/build-small-hackathon/turboskillslug-shell-from-session)

---

*The slug watches, gives its gifts, and goes back to sleep.*
*I was here.*
