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
---

# TurboSkillSlug

*A small, slow companion who sits beside you while you build.*

Upload a recording of your build session. You narrating what you're trying, what's failing, what finally works. The slug will sit quietly through it, then give you three gifts:

1. **A slug recap** in their gentle voice, each observation grounded in something that actually happened
2. **A SKILL.md** with the structured record of your session: what you tried, why it failed, the breakthrough, the gotchas
3. **A shell** whose spiral, knots, jewels, and colors are all derived from the shape of your work

Every shell is unique because every build session is unique.

## How the shell reads your session

| What happened in your session | How the shell shows it |
|---|---|
| Duration | Overall size and number of spiral turns |
| Each approach you tried | Spiral arm density |
| Each dead end | A dark knot on the spiral body |
| The breakthrough moment | The glowing aperture at the spiral's tip |
| Gotchas you hit | Iridescent jewels along the outer rim |
| Your emotional arc | Color gradient from start to end |

The shell uses procedural SVG with nacre (mother of pearl) texture filters, HSL derived color harmonies, and bezier smoothed curves. No two shells look the same because the geometry is seeded by your session's actual structure.

## The models

| Model | Parameters | Role |
|---|---|---|
| `openai/whisper-large-v3-turbo` | 809M | Transcribes your audio |
| `Qwen/Qwen2.5-7B-Instruct` | 7B | Extracts session structure and writes the slug's voice |
| **Total** | **~7.8B** | Well under the Build Small 32B cap |

Both models run via the Hugging Face Inference API. The slug holds no memory across sessions. It watches, gives its gifts, and goes back to sleep.

## Built with OpenAI Codex

This project was built using [OpenAI Codex](https://openai.com/codex) as the primary coding agent. The full commit history is in the public GitHub repo:

**[github.com/AnubhavBharadwaaj/turbo-skill-slug](https://github.com/AnubhavBharadwaaj/turbo-skill-slug)**

### How Codex built this

Codex was given one task at a time, each scoped as a single pull request:

- **PR #1: Scaffold** Codex created the Gradio app skeleton, requirements, HF Space YAML, .gitignore, and the first test. It seeded the main branch and opened the PR with clean attribution.
- **PR #2: Shell SVG generator** Codex took a reference implementation of the logarithmic spiral geometry, productionized it with type hints and docstrings, wired it into the Gradio app with inline preview and downloadable files, and added the shell test. All four tests green before merge.
- **Subsequent commits** addressed deployment fixes (Gradio version compatibility, Inference API provider routing, audio content type handling) and extraction prompt tightening (constrained sentiment vocabulary, grounded slug voice, structured SKILL.md validation).

Every commit in the repo is attributed to Codex or to the builder responding to Codex's work. The branch naming convention (`codex/scaffold-*`, `codex/shell-svg-generator`) preserves the lineage.

### What Codex was good at

Scaffolding, test writing, dependency wiring, and mechanical refactoring. Codex handled the Gradio component plumbing and pytest mocking without hand holding.

### What needed human judgment

The slug's voice (50 hand written seed utterances that define the tone), the shell's visual design (procedural SVG tuning for beauty, not just correctness), and the extraction prompt's grounding constraints (ensuring the slug never claims to witness something the transcript does not support).

## Built for the Build Small hackathon

> *Strange is good. Joyful is the bar.*

The slug is strange. The shell is joyful. Both are small.
