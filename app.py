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

ProcessAudioResult = tuple[str, str, str, str, str | None, str | None, str | None]


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


def _write_download_file(filename: str, content: str) -> str:
    """Write generated content to a temporary file for Gradio download output."""
    download_dir = Path(tempfile.mkdtemp(prefix="turboskillslug-"))
    path = download_dir / filename
    path.write_text(content, encoding="utf-8")
    return str(path)


def process_audio(audio: str | None) -> ProcessAudioResult:
    """Transcribe an uploaded or recorded audio file and extract a session recap."""
    if audio is None:
        message = "Give the slug an audio file first."
        return message, "", "", "", None, None, None

    transcript = transcribe_audio(audio)
    extraction = extract_session(transcript)
    slug_recap = _format_slug_recap(extraction)
    shell_svg = generate_shell_svg(extraction)
    raw_json = json.dumps(extraction, indent=2)
    shell_file = _write_download_file("turboskillslug-shell.svg", shell_svg)
    skill_file = _write_download_file("SKILL.md", str(extraction.get("skill_md", "")))
    recap_file = _write_download_file("slug-recap.txt", slug_recap)

    return (
        f"## Transcript\n\n{transcript}",
        slug_recap,
        shell_svg,
        raw_json,
        shell_file,
        skill_file,
        recap_file,
    )


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
        shell_output = gr.HTML(label="Shell")
        raw_json_output = gr.Code(label="Raw JSON", language="json")
        shell_download = gr.File(label="Download shell SVG")
        skill_download = gr.File(label="Download SKILL.md")
        recap_download = gr.File(label="Download slug recap")

        submit_button.click(
            fn=process_audio,
            inputs=audio_input,
            outputs=[
                transcript_output,
                recap_output,
                shell_output,
                raw_json_output,
                shell_download,
                skill_download,
                recap_download,
            ],
        )

    return demo


interface = build_interface()


if __name__ == "__main__":
    interface.launch()
