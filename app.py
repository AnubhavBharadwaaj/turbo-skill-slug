"""TurboSkillSlug Gradio application."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any

import gradio as gr

from extract import extract_session
from shell import generate_shell_svg
from transcribe import transcribe_audio


def _format_slug_recap(extraction: dict[str, Any]) -> str:
    """Format structured extraction data for the Gradio recap panel."""
    slug_voice = extraction.get("slug_voice", [])
    utterances = "\n".join(f"*{u}*" for u in slug_voice)
    themes = ", ".join(extraction.get("themes", []))

    return (
        "## what the slug witnessed\n\n"
        f"{utterances}\n\n"
        f"**Duration:** {extraction.get('duration_minutes')} minutes\n\n"
        f"**Themes:** {themes}\n"
    )


def process_audio(
    audio: str | None,
) -> tuple[str, str, str, str, str | None, str | None, str | None]:
    """Transcribe, extract, generate shell, and return all outputs."""
    if audio is None:
        message = "Give the slug an audio file first."
        return message, "", "", "", None, None, None

    # 1. Transcribe
    transcript = transcribe_audio(audio)

    # 2. Extract session features + slug voice
    extraction = extract_session(transcript)
    raw_json = json.dumps(extraction, indent=2)

    # 3. Generate the shell SVG
    shell_svg = generate_shell_svg(extraction)

    # 4. Write downloadable files
    tmp_dir = Path(tempfile.mkdtemp(prefix="slug_"))

    svg_path = tmp_dir / "shell.svg"
    svg_path.write_text(shell_svg)

    skill_path = tmp_dir / "skill.md"
    skill_path.write_text(extraction.get("skill_md", ""))

    recap_lines = extraction.get("slug_voice", [])
    recap_path = tmp_dir / "slug_recap.txt"
    recap_path.write_text("\n\n".join(recap_lines))

    return (
        f"## Transcript\n\n{transcript}",
        _format_slug_recap(extraction),
        shell_svg,
        raw_json,
        str(svg_path),
        str(skill_path),
        str(recap_path),
    )


def build_interface() -> gr.Blocks:
    """Build and return the TurboSkillSlug Gradio Blocks interface."""
    with gr.Blocks(title="TurboSkillSlug") as demo:
        gr.Markdown(
            "# 🐌 TurboSkillSlug\n\n"
            "*A small, slow companion who watches you build.*\n\n"
            "Upload a recording of your build session. The slug will sit quietly through it, "
            "then give you a gentle recap, a clean SKILL.md, and a hand-grown shell."
        )

        with gr.Row():
            with gr.Column(scale=1):
                audio_input = gr.Audio(
                    sources=["upload", "microphone"],
                    type="filepath",
                    label="your build session",
                )
                submit_button = gr.Button(
                    "🐌 give it to the slug", variant="primary"
                )
            with gr.Column(scale=2):
                recap_output = gr.Markdown(label="slug recap")
                shell_output = gr.HTML(label="your shell")

        transcript_output = gr.Markdown(label="transcript")
        raw_json_output = gr.Code(label="Raw JSON", language="json")

        with gr.Row():
            svg_download = gr.File(label="shell.svg")
            skill_download = gr.File(label="skill.md")
            recap_download = gr.File(label="slug_recap.txt")

        submit_button.click(
            fn=process_audio,
            inputs=audio_input,
            outputs=[
                transcript_output,
                recap_output,
                shell_output,
                raw_json_output,
                svg_download,
                skill_download,
                recap_download,
            ],
        )

    return demo


interface = build_interface()

if __name__ == "__main__":
    interface.launch()
