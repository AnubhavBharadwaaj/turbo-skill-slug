"""TurboSkillSlug Gradio application."""

from __future__ import annotations

import base64 as b64lib
import json
import os
import tempfile
import wave
from pathlib import Path
from typing import Any

import gradio as gr
import httpx

from extract import extract_session
from receipt import generate_receipt_svg
from shell import generate_shell_svg
from transcribe import transcribe_audio


SLUGVOICE_URL = os.environ.get(
    "MODAL_SLUGVOICE_URL",
    "https://anubhavbharadwaaj--slugvoice-serve-slugvoiceserver-api.modal.run",
)
TTS_URL = os.environ.get(
    "MODAL_TTS_URL",
    "https://anubhavbharadwaaj--slugvoice-tts-slugtts-api.modal.run",
)


def _get_slugvoice(transcript: str) -> list[str] | None:
    """Call the fine-tuned SlugVoice model on Modal."""
    try:
        resp = httpx.post(
            SLUGVOICE_URL,
            json={"transcript": transcript},
            timeout=60,
        )
        resp.raise_for_status()
        return resp.json().get("slug_voice")
    except Exception as e:
        print(f"SlugVoice Modal call failed, falling back to Qwen: {e}")
        return None


def _speak_recap(slug_lines: list[str]) -> str | None:
    """Convert slug recap to speech via Chatterbox on Modal."""
    try:
        full_text = ". ".join(slug_lines) + ". I was here."
        resp = httpx.post(TTS_URL, json={"text": full_text}, timeout=120)
        resp.raise_for_status()
        audio_b64 = resp.json().get("audio", "")
        if audio_b64:
            audio_bytes = b64lib.b64decode(audio_b64)
            tmp = Path(tempfile.mkdtemp()) / "slug_speaks.wav"
            tmp.write_bytes(audio_bytes)
            return str(tmp)
    except Exception as e:
        print(f"TTS failed: {e}")
    return None


def _get_audio_duration_minutes(file_path: str) -> float:
    """Get actual audio duration in minutes from the file itself."""
    try:
        with wave.open(file_path, "r") as f:
            return (f.getnframes() / f.getframerate()) / 60
    except Exception:
        try:
            size = os.path.getsize(file_path)
            return round(size / (32000 * 60), 1)
        except Exception:
            return 1.0


def _format_slug_recap(extraction: dict[str, Any]) -> str:
    """Format the slug's witness recap for display."""
    slug_voice = extraction.get("slug_voice", [])
    utterances = "\n\n".join(f"*{u}*" for u in slug_voice)

    # The slug's closing signature
    utterances += "\n\n*I was here.*"

    themes = ", ".join(extraction.get("themes", []))
    duration = extraction.get("duration_minutes", 0)

    return (
        "## what the slug witnessed\n\n"
        f"{utterances}\n\n"
        f"**Duration:** {duration} minutes\n\n"
        f"**Themes:** {themes}\n"
    )


def process_audio(
    audio: str | None,
) -> tuple[
    str,
    str,
    str,
    str,
    str,
    str | None,
    str | None,
    str | None,
    str | None,
    str | None,
]:
    """Transcribe, extract, generate shell, and return all outputs."""
    if audio is None:
        message = "Give the slug an audio file first."
        return message, "", "", "", "", None, None, None, None, None

    # 1. Transcribe
    transcript = transcribe_audio(audio)

    # 2. Extract session features + slug voice
    extraction = extract_session(transcript)

    # 3. Replace slug_voice with fine-tuned model output
    slugvoice_lines = _get_slugvoice(transcript)
    if slugvoice_lines:
        extraction["slug_voice"] = slugvoice_lines

    slug_audio_path = _speak_recap(extraction.get("slug_voice", []))

    # 4. Override duration with actual audio length
    extraction["duration_minutes"] = round(
        _get_audio_duration_minutes(audio), 1
    )

    raw_json = json.dumps(extraction, indent=2)

    # 5. Generate the shell SVG
    shell_svg = generate_shell_svg(extraction)
    receipt_svg = generate_receipt_svg(extraction)

    # 6. Write downloadable files
    tmp_dir = Path(tempfile.mkdtemp(prefix="slug_"))

    svg_path = tmp_dir / "shell.svg"
    svg_path.write_text(shell_svg)

    receipt_path = tmp_dir / "receipt.svg"
    receipt_path.write_text(receipt_svg)

    skill_path = tmp_dir / "skill.md"
    skill_path.write_text(extraction.get("skill_md", ""))

    recap_lines = extraction.get("slug_voice", [])
    recap_lines.append("I was here.")
    recap_path = tmp_dir / "slug_recap.txt"
    recap_path.write_text("\n\n".join(recap_lines))

    return (
        f"## Transcript\n\n{transcript}",
        _format_slug_recap(extraction),
        shell_svg,
        receipt_svg,
        raw_json,
        slug_audio_path,
        str(svg_path),
        str(receipt_path),
        str(skill_path),
        str(recap_path),
    )


def build_interface() -> gr.Blocks:
    """Build and return the TurboSkillSlug Gradio Blocks interface."""
    with gr.Blocks(title="TurboSkillSlug") as demo:
        gr.Markdown(
            "# 🐌 TurboSkillSlug\n\n"
            "*A small, slow companion who watches you build.*\n\n"
            "Upload a recording of your build session. The slug will sit "
            "quietly through it, then give you a gentle recap, a clean "
            "SKILL.md, and a hand-grown shell."
        )

        with gr.Row():
            with gr.Column(scale=1):
                audio_input = gr.Audio(
                    sources=["upload", "microphone"],
                    type="filepath",
                    label="your build session",
                )
                gr.Examples(
                    examples=["sample_session.wav"],
                    inputs=audio_input,
                    label="or try a sample session",
                )
                submit_button = gr.Button(
                    "🐌 give it to the slug", variant="primary"
                )
            with gr.Column(scale=2):
                recap_output = gr.Markdown(label="slug recap")
                slug_audio = gr.Audio(label="the slug speaks", type="filepath")
                shell_output = gr.HTML(label="your shell")
                receipt_output = gr.HTML(label="your receipt")

        transcript_output = gr.Markdown(label="transcript")
        raw_json_output = gr.Code(label="Raw JSON", language="json")

        with gr.Row():
            svg_download = gr.File(label="shell.svg")
            receipt_download = gr.File(label="receipt.svg")
            skill_download = gr.File(label="skill.md")
            recap_download = gr.File(label="slug_recap.txt")

        submit_button.click(
            fn=process_audio,
            inputs=audio_input,
            outputs=[
                transcript_output,
                recap_output,
                shell_output,
                receipt_output,
                raw_json_output,
                slug_audio,
                svg_download,
                receipt_download,
                skill_download,
                recap_download,
            ],
        )

    return demo


interface = build_interface()

if __name__ == "__main__":
    interface.launch()
