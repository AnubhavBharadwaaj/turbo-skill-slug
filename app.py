"""TurboSkillSlug Gradio application."""

from __future__ import annotations

import json
from typing import Any

import gradio as gr

from extract import extract_session
from transcribe import transcribe_audio


def _format_slug_recap(extraction: dict[str, Any]) -> str:
    """Format structured extraction data for the Gradio recap panel."""
    slug_voice = extraction.get("slug_voice", [])
    utterances = "\n".join(f"- {utterance}" for utterance in slug_voice)
    themes = ", ".join(extraction.get("themes", []))
    skill_md = extraction.get("skill_md", "")

    return (
        "## Slug recap\n\n"
        f"**Duration:** {extraction.get('duration_minutes')} minutes\n\n"
        f"**Themes:** {themes}\n\n"
        "### Slug voice\n"
        f"{utterances}\n\n"
        "### Draft SKILL.md\n"
        f"```markdown\n{skill_md}\n```"
    )


def process_audio(audio: str | None) -> tuple[str, str, str]:
    """Transcribe an uploaded or recorded audio file and extract a session recap."""
    if audio is None:
        message = "Give the slug an audio file first."
        return message, "", ""

    transcript = transcribe_audio(audio)
    extraction = extract_session(transcript)
    raw_json = json.dumps(extraction, indent=2)

    return f"## Transcript\n\n{transcript}", _format_slug_recap(extraction), raw_json


def build_interface() -> gr.Blocks:
    """Build and return the TurboSkillSlug Gradio Blocks interface."""
    with gr.Blocks(title="TurboSkillSlug") as demo:
        gr.Markdown(
            "# TurboSkillSlug\n"
            "A tiny audio-first Space where the slug will eventually size up your skills."
        )
        audio_input = gr.Audio(
            sources=["upload", "microphone"],
            type="filepath",
            label="Audio",
        )
        submit_button = gr.Button("give it to the slug")
        transcript_output = gr.Markdown()
        recap_output = gr.Markdown()
        raw_json_output = gr.Code(label="Raw JSON", language="json")

        submit_button.click(
            fn=process_audio,
            inputs=audio_input,
            outputs=[transcript_output, recap_output, raw_json_output],
        )

    return demo


interface = build_interface()


if __name__ == "__main__":
    interface.launch()
