---
title: TurboSkillSlug
emoji: 🐌
colorFrom: purple
colorTo: yellow
sdk: gradio
sdk_version: "5.0.0"
python_version: "3.12"
app_file: app.py
pinned: false
short_description: A small slow companion who watches you build.
tags:
  - hackathon
  - build-small-hackathon
---

# 🐌 TurboSkillSlug

> A small, slow companion who sits beside you while you build. They watch
> for an hour, never judging, taking patient notes in their head. When
> you're done — when you finally whisper *"got it"* — TurboSkillSlug gives
> you two gifts: a soft retelling of your session in their gentle slug-voice
> (your dead ends sound dignified, your breakthroughs sound earned), and a
> hand-grown shell, its patterns generated from the rhythm of your work.
> Every spiral is a thing you tried. Every iridescent band is a moment you
> almost gave up. The shell is yours to keep. The slug will be there next time.

## What you get back

1. **A slug recap** — five short utterances in the slug's earnest voice,
   each grounded in something that actually happened in your session
2. **A SKILL.md** — a clean, structured record of what you tried, what
   failed, what worked, and the gotchas to remember
3. **A shell** — a one-of-a-kind SVG whose shape, color, and patterns are
   derived from the rhythm of your work

## How the shell is made

| What happened | How the shell shows it |
|---|---|
| Session duration | overall size and spiral length |
| Each approach tried | spiral arm density |
| Each dead end | a dark knot on the spiral body |
| The breakthrough | the aperture (mouth) at the spiral's tip |
| Gotchas captured | small iridescent jewels along the outer rim |
| Sentiment arc | gradient from start-color to end-color |

## The models

- `openai/whisper-small` — transcribes your audio
- `Qwen/Qwen2.5-7B-Instruct` — extracts session structure + writes the slug's voice
- Total: **≈ 7.25B parameters** (well under the build-small 32B cap)

Both run on the Hugging Face Inference API. The slug remembers nothing
across sessions — it watches, gives, and goes back to sleep.

## Built for the Build Small hackathon

> _Strange is good. Joyful is the bar._
