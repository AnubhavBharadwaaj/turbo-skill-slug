# Codex Build Log: TurboSkillSlug

TurboSkillSlug was built as a small Gradio app with Codex acting as the primary coding partner. The project began as an empty repository and grew into a Hugging Face Space that accepts a build-session audio recording, transcribes it, extracts a structured recap, writes a draft `SKILL.md`, and generates a procedural SVG shell from the shape of the session.

This log summarizes how Codex was used, what it implemented, where development got sticky, and what the project taught us.

## Starting Point

The first Codex work was straightforward scaffolding:

- Created the Gradio app shell in `app.py`.
- Added `requirements.txt`, `.gitignore`, and Hugging Face Space metadata in `README.md`.
- Added the first tests under `tests/`.
- Set up the basic "upload audio, return output" flow.

That initial phase was the part Codex handled most naturally: file structure, simple UI wiring, dependency declarations, and tests.

## Features Codex Implemented

### Audio Transcription

Codex added `transcribe.py` to send uploaded audio to `openai/whisper-large-v3-turbo` through Hugging Face. This went through several iterations:

- Started with `InferenceClient`.
- Pinned and adjusted Gradio and Python versions to handle Space launch issues.
- Tried provider-specific routing and file-path based ASR calls.
- Tried raw bytes and `BytesIO`.
- Finally bypassed `InferenceClient` for transcription and used a direct `httpx` POST to the HF router with an explicit `Content-Type`.

The final lesson was simple: for this ASR path, explicit HTTP was more reliable than fighting provider abstractions.

### Session Extraction

Codex added `extract.py` to call `Qwen/Qwen2.5-7B-Instruct` and produce:

- `duration_minutes`
- `themes`
- `approaches_tried`
- `dead_ends`
- `breakthroughs`
- `gotchas`
- `sentiment_arc`
- `skill_md`
- `slug_voice`

This became the emotional center of the project. The extraction prompt had to do more than produce valid JSON; it had to preserve the core promise of the app: the slug is a witness, not a generic summary writer.

Codex iterated on:

- strict JSON parsing
- required output keys
- constrained sentiment labels
- graceful validation and patching for imperfect model output
- structured `skill_md` sections
- rules forcing `slug_voice` to reference transcript-specific moments
- dead-end counting rules so smooth sessions stay smooth and messy sessions show their mess

The final prompt removes copyable gold-set examples and instead describes behavior directly. That change came from testing: when examples were present, Qwen copied them verbatim across sessions.

### Shell SVG Generation

Codex added `shell.py`, a procedural SVG generator that turns session structure into visual form:

- duration affects size and spiral complexity
- approaches affect spiral density
- dead ends become dark knots
- gotchas become rim jewels
- breakthroughs affect the glowing aperture
- sentiment arc drives the color story

Later commits polished the shell with nacre texture, rim glow, HSL palettes, and a central eye. This was where correctness alone was not enough; the shell had to feel demo-worthy.

### Gradio App Wiring

Codex wired the full pipeline in `app.py`:

- upload or record audio
- transcribe with Whisper
- extract structured session data with Qwen
- override duration with the real audio length
- render the slug recap
- render the shell SVG inline
- expose raw JSON
- write downloadable `shell.svg`, `skill.md`, and `slug_recap.txt`
- include a sample session in the UI

The interface became a two-column app: input on the left, recap and shell on the right.

### Documentation And Deployment

Codex helped maintain the README and deployment support:

- Hugging Face Space frontmatter
- model table and parameter count
- shell interpretation table
- demo and social links
- tags for the Build Small hackathon
- deployment script for HF Space remotes

The history also includes deploy commits to Hugging Face Space remotes, separate from the main GitHub history.

## Challenges During Development

### Provider Routing Was Fragile

The Hugging Face provider layer behaved differently for Whisper and Qwen. Whisper needed the `hf-inference` route at first, while Qwen needed automatic routing. Then Whisper still failed because content type was not being set correctly for audio bytes. The reliable fix was a direct `httpx` request.

Codex was useful here because it could keep applying narrow fixes quickly, but the development lesson was to stop abstracting once the abstraction became the problem.

### Gradio And Python Compatibility

Several commits adjusted runtime compatibility:

- pinned Python 3.12 to avoid `audioop` removal issues in Python 3.13
- pinned and then bumped Gradio versions to fix schema and launch errors
- added required Hugging Face Space metadata

These were not glamorous changes, but they were the difference between a local idea and a deployable demo.

### The Slug Voice Was The Hardest Part

The most important failure was also the most instructive: the slug started copying example utterances word for word.

The intent was to show tone, but the model treated the examples as content. That produced the exact failure mode the project was trying to avoid: a supposedly present witness saying generic lines that did not happen in the session.

The prompt eventually moved away from examples and toward hard behavioral rules:

- every line must reference this transcript
- use concrete details such as tools, errors, variable names, and actions
- never summarize, advise, or invent
- if there is no evidence, stay silent

That changed the prompt from "write in this style" to "obey this witness contract."

### Validators Had To Be Gentle

Early validation crashed when Qwen missed required `skill_md` sections. That was technically correct but bad product behavior. The app should still show the transcript, recap, shell, and downloads even if one structured field is imperfect.

Codex changed the validators to patch or clamp where possible:

- missing `skill_md` sections get stubbed with `_(not captured)_`
- invalid sentiment values map to the closest allowed label
- missing slug voice lines are padded rather than killing the whole request

The lesson was to validate for resilience, not purity.

### Dead Ends And Sentiment Needed Rubrics

Testing three different scripts revealed extraction bias:

- too few dead ends in messy sessions
- invented dead ends in clean sessions
- endings defaulting to `resolved`

Codex added explicit rubrics so the model knew that:

- every failed approach is a dead end
- clean explorations should have no dead ends
- quick pleasant sessions can end `joyful`
- long draining sessions can end `exhausted`
- `resolved` is only for a clear bug-fix arc

This made the shell's visual grammar more honest, because the shell depends directly on those extracted features.

## What Was Learned

Codex was strongest when the task could be expressed as concrete code movement: scaffold this app, add this module, wire these outputs, parse this JSON, commit and push this exact fix.

The human role mattered most where taste and truth mattered:

- deciding what the slug should sound like
- noticing when "technically valid" output felt false
- tuning the shell from generated geometry into something delightful
- deciding when a model failure should be patched instead of treated as fatal

The project also showed that prompt engineering is product engineering. The prompt is not just instruction text; it is part of the app's behavior, reliability, and user trust.

## Final Shape

TurboSkillSlug now works as a complete small demo:

1. The user uploads a narrated build session.
2. Whisper transcribes it.
3. Qwen extracts the session structure and writes the slug's witness lines.
4. The app renders a recap and a procedural shell.
5. The user can download the shell SVG, draft `SKILL.md`, and slug recap.

The result is intentionally small, strange, and specific. Codex built most of the machinery. The repeated tests and corrections taught it where the machinery needed to become more honest.
