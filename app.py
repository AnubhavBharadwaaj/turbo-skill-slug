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
from trace_parser import parse_trace_to_transcript, detect_trace_format


TTS_URL = os.environ.get(
    "MODAL_TTS_URL",
    "https://anubhavbharadwaaj--slugvoice-tts-slugtts-api.modal.run",
)


def _speak_recap(slug_lines: list[str]) -> str | None:
    """Convert slug recap to speech via Chatterbox on Modal."""
    try:
        full_text = ". ".join(slug_lines) + ". I was here."
        resp = httpx.post(TTS_URL, json={"text": full_text}, timeout=180)
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


def on_audio_change(audio: str | None):
    """Fired the moment a file is selected/recorded/cleared.

    Disables the button and shows a 'preparing' state during the window
    after upload but before the user can meaningfully click submit, so a
    premature click is impossible and there is always visible feedback.
    """
    if audio is None:
        return (
            gr.update(value="🐌 give it to the slug", interactive=False),
            gr.update(value=""),
        )
    return (
        gr.update(value="🐌 give it to the slug", interactive=True),
        gr.update(value="*The slug is ready. Hand it your session.*"),
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

    # 2. Extract session features + slug voice.
    #    extract_session uses the Modal dual-adapter endpoint:
    #    extraction LoRA for the JSON, voice LoRA for slug_voice.
    #    The 7B is only a labeled fallback inside extract_session.
    extraction = extract_session(transcript)

    # 3. Speak the recap aloud (Chatterbox TTS on Modal)
    slug_audio_path = _speak_recap(extraction.get("slug_voice", []))

    # 4. Reconcile duration. The model estimates the DESCRIBED session length
    #    from the transcript ("three hours on one problem"); the audio file
    #    gives the NARRATION length. A real-time narration makes these agree;
    #    a compressed retelling makes the audio far shorter than the real
    #    session. Take the larger so the shell reflects the work, not the
    #    speaking time.
    audio_minutes = round(_get_audio_duration_minutes(audio), 1)
    model_minutes = extraction.get("duration_minutes", 0)
    try:
        model_minutes = float(model_minutes)
    except (TypeError, ValueError):
        model_minutes = 0.0
    extraction["duration_minutes"] = round(max(audio_minutes, model_minutes), 1)

    raw_json = json.dumps(extraction, indent=2)

    # 5. Generate the shell + receipt SVGs
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

    # Build recap text WITHOUT mutating the extraction's slug_voice list
    recap_lines = list(extraction.get("slug_voice", [])) + ["I was here."]
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



def process_trace(trace_file: str | None):
    """Parse an agent session JSONL trace and run it through the same pipeline.

    A Claude Code or Codex CLI session log becomes witness testimony the slug
    reads exactly like a spoken transcript. This is the input judges can feed
    from their own machines.
    """
    if trace_file is None:
        message = "Drop a Claude Code or Codex session trace first."
        return message, "", "", "", "", None, None, None, None, None

    try:
        with open(trace_file, "r", encoding="utf-8", errors="replace") as f:
            jsonl_string = f.read()
    except Exception as e:
        return f"Could not read the trace: {e}", "", "", "", "", None, None, None, None, None

    source = detect_trace_format(jsonl_string)
    transcript = parse_trace_to_transcript(jsonl_string)
    if not transcript:
        return (
            "The slug could not find a session in that file.",
            "", "", "", "", None, None, None, None, None,
        )

    # From here, identical to the audio path: extract, generate, render.
    extraction = extract_session(transcript)
    slug_audio_path = _speak_recap(extraction.get("slug_voice", []))

    # Duration: no audio file, so trust the model's estimate of the described
    # session length. Fall back to a minimum if the model gave nothing.
    model_minutes = extraction.get("duration_minutes", 0)
    try:
        model_minutes = float(model_minutes)
    except (TypeError, ValueError):
        model_minutes = 0.0
    extraction["duration_minutes"] = round(model_minutes, 1) if model_minutes > 0 else 1.0

    raw_json = json.dumps(extraction, indent=2)
    shell_svg = generate_shell_svg(extraction)
    receipt_svg = generate_receipt_svg(extraction)

    tmp_dir = Path(tempfile.mkdtemp(prefix="slug_trace_"))
    svg_path = tmp_dir / "shell.svg"
    svg_path.write_text(shell_svg)
    receipt_path = tmp_dir / "receipt.svg"
    receipt_path.write_text(receipt_svg)
    skill_path = tmp_dir / "skill.md"
    skill_path.write_text(extraction.get("skill_md", ""))
    recap_lines = list(extraction.get("slug_voice", [])) + ["I was here."]
    recap_path = tmp_dir / "slug_recap.txt"
    recap_path.write_text("\n\n".join(recap_lines))

    label = {"claude": "Claude Code", "codex": "Codex CLI"}.get(source, "agent")
    transcript_display = (
        f"## Session trace ({label})\n\n"
        f"The slug read your {label} session and witnessed this:\n\n{transcript}"
    )

    return (
        transcript_display,
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
                with gr.Tabs():
                    with gr.Tab("narrate aloud"):
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
                            "🐌 give it to the slug", variant="primary",
                            interactive=False,
                        )
                        status_line = gr.Markdown("")
                    with gr.Tab("drop a session trace"):
                        gr.Markdown(
                            "Drag a **Claude Code** "
                            "(`~/.claude/projects/.../*.jsonl`) or **Codex CLI** "
                            "(`~/.codex/sessions/.../*.jsonl`) session log. "
                            "The slug reads your actual work, no narration needed."
                        )
                        trace_input = gr.File(
                            label="session trace (.jsonl)",
                            file_types=[".jsonl"],
                            type="filepath",
                        )
                        gr.Examples(
                            examples=["sample_trace.jsonl"],
                            inputs=trace_input,
                            label="or try a sample trace",
                        )
                        trace_button = gr.Button(
                            "🐌 let the slug read it", variant="primary",
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

        # Enable the button + show readiness only once audio is actually present
        audio_input.change(
            fn=on_audio_change,
            inputs=audio_input,
            outputs=[submit_button, status_line],
        )

        # On click: immediately show a working state, then run the pipeline
        submit_button.click(
            fn=lambda: (
                gr.update(value="🐌 the slug is watching…", interactive=False),
                gr.update(value="*The slug is listening. This takes a moment.*"),
            ),
            inputs=None,
            outputs=[submit_button, status_line],
        ).then(
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
        ).then(
            fn=lambda: (
                gr.update(value="🐌 give it to the slug", interactive=True),
                gr.update(value="*The slug has finished. Scroll down for your gifts.*"),
            ),
            inputs=None,
            outputs=[submit_button, status_line],
        )

        # Trace path: parse JSONL -> same pipeline, same outputs
        trace_button.click(
            fn=process_trace,
            inputs=trace_input,
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
