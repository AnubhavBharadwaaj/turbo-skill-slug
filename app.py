"""TurboSkillSlug Gradio application."""

from __future__ import annotations

import base64 as b64lib
import json
import os
import tempfile
import time
import wave
from pathlib import Path
from typing import Any

import gradio as gr
import httpx

from extract import extract_session
from receipt import generate_receipt_svg
from shell import generate_shell_svg
from shell_animate import wrap_in_iframe
from shell_unroll import build_unroll_doc, N_STAGES
from gallery_client import save_shell, list_shells, get_shell
from shell_animate import wrap_in_iframe as _wrap_iframe
from transcribe import transcribe_audio
from trace_parser import parse_trace_to_transcript, detect_trace_format


# Growth stages for the live shell reveal. The slug grows the shell as it
# watches: spiral lengthens, knots and jewels form in order, aperture opens last.
GROWTH_STAGES = [0.18, 0.38, 0.58, 0.78, 1.0]
GROWTH_PACING_SECONDS = 0.55  # brief pause between stages so the eye sees growth

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


def _empty_outputs(message: str):
    """Twelve-tuple matching the output components, for early/error yields."""
    return (message, "", "", "", "", None, None, None, None, None, None, None)


def _finalize_outputs(transcript_display: str, extraction: dict, slug_audio_path):
    """Build the full ten-tuple of outputs once the shell is fully grown.

    Shared by the audio and trace paths so both render identically.
    """
    raw_json = json.dumps(extraction, indent=2)
    # The full static shell is what we save for download (clean, portable).
    shell_svg = generate_shell_svg(extraction, growth=1.0)
    # For the live display, build the scroll-unroll: a flipbook of growth stages
    # (each truncates the spiral ALONG its arm) led by a 3D paper curl riding the
    # tip. This lays the parchment down along the spiral path, not radially.
    try:
        stages = [
            generate_shell_svg(extraction, growth=(i + 1) / N_STAGES)
            for i in range(N_STAGES)
        ]
        unroll_doc = build_unroll_doc(stages)
        shell_display = wrap_in_iframe(unroll_doc, height=660)
    except Exception:
        # Never let the animation break the result: fall back to the static shell.
        shell_display = wrap_in_iframe(shell_svg, height=660)
    receipt_svg = generate_receipt_svg(extraction)

    tmp_dir = Path(tempfile.mkdtemp(prefix="slug_"))
    svg_path = tmp_dir / "shell.svg"
    svg_path.write_text(shell_svg)
    receipt_path = tmp_dir / "receipt.svg"
    receipt_path.write_text(receipt_svg)
    skill_path = tmp_dir / "skill.md"
    skill_path.write_text(extraction.get("skill_md", ""))
    recap_lines = list(extraction.get("slug_voice", [])) + ["I was here."]
    recap_path = tmp_dir / "slug_recap.txt"
    recap_path.write_text("\n\n".join(recap_lines))

    return (
        transcript_display,
        _format_slug_recap(extraction),
        shell_display,
        receipt_svg,
        raw_json,
        slug_audio_path,
        str(svg_path),
        str(receipt_path),
        str(skill_path),
        str(recap_path),
        shell_svg,        # static SVG, for the "keep this shell" gallery save
        extraction,       # metadata, for the gallery entry
    )


def _grow_shell_stages(extraction: dict, transcript_display: str):
    """Yield a single 'shaping' status while the browser-played birth animation
    is prepared. The smooth growth now happens in the browser (shards / draw /
    glass), so we no longer stream mechanical server-side frames. One gentle
    status, then the caller yields the finished animated shell.
    """
    yield (
        "*The slug is shaping your shell...*",
        "*the shell is coming into being...*",
        "", "", "", None, None, None, None, None, None, None,
    )


def process_audio(audio: str | None):
    """Transcribe, extract, then GROW the shell live, yielding each stage."""
    if audio is None:
        yield _empty_outputs("Give the slug an audio file first.")
        return

    transcript = transcribe_audio(audio)
    extraction = extract_session(transcript)
    slug_audio_path = _speak_recap(extraction.get("slug_voice", []))

    audio_minutes = round(_get_audio_duration_minutes(audio), 1)
    model_minutes = extraction.get("duration_minutes", 0)
    try:
        model_minutes = float(model_minutes)
    except (TypeError, ValueError):
        model_minutes = 0.0
    extraction["duration_minutes"] = round(max(audio_minutes, model_minutes), 1)

    transcript_display = f"## Transcript\n\n{transcript}"
    yield from _grow_shell_stages(extraction, transcript_display)
    yield _finalize_outputs(transcript_display, extraction, slug_audio_path)



def process_trace(trace_file: str | None):
    """Parse an agent session JSONL trace, then GROW the shell live.

    A Claude Code or Codex CLI session log becomes witness testimony the slug
    reads exactly like a spoken transcript. This is the input judges can feed
    from their own machines.
    """
    if trace_file is None:
        yield _empty_outputs("Drop a Claude Code or Codex session trace first.")
        return

    try:
        with open(trace_file, "r", encoding="utf-8", errors="replace") as f:
            jsonl_string = f.read()
    except Exception as e:
        yield _empty_outputs(f"Could not read the trace: {e}")
        return

    source = detect_trace_format(jsonl_string)
    transcript = parse_trace_to_transcript(jsonl_string)
    if not transcript:
        yield _empty_outputs("The slug could not find a session in that file.")
        return

    extraction = extract_session(transcript)
    slug_audio_path = _speak_recap(extraction.get("slug_voice", []))

    # Duration: no audio file, so trust the model's estimate.
    model_minutes = extraction.get("duration_minutes", 0)
    try:
        model_minutes = float(model_minutes)
    except (TypeError, ValueError):
        model_minutes = 0.0
    extraction["duration_minutes"] = round(model_minutes, 1) if model_minutes > 0 else 1.0

    label = {"claude": "Claude Code", "codex": "Codex CLI"}.get(source, "agent")
    transcript_display = (
        f"## Session trace ({label})\n\n"
        f"The slug read your {label} session and witnessed this:\n\n{transcript}"
    )

    yield from _grow_shell_stages(extraction, transcript_display)
    yield _finalize_outputs(transcript_display, extraction, slug_audio_path)


def build_interface() -> gr.Blocks:
    """Build and return the TurboSkillSlug Gradio Blocks interface."""
    with gr.Blocks(title="TurboSkillSlug") as demo:
        gr.Markdown(
            "# 🐌 TurboSkillSlug\n\n"
            "*A small, slow companion who watches you build.*\n\n"
            "Give the slug a build session: narrate it aloud, or drop an agent "
            "session trace. It watches, then grows you a shell, a recap, a "
            "SKILL.md, and a receipt."
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
            with gr.Column(scale=1):
                status_line = gr.Markdown("")

        # ---- THE SHELL, front and center, right under the inputs ----
        # This is what plays during generation. Everything else stays hidden
        # until the shell has finished being born.
        shell_output = gr.HTML(label="your shell")

        # ---- EVERYTHING ELSE, hidden until the shell finishes ----
        with gr.Group(visible=False) as gifts_group:
            gr.Markdown("### the slug's other gifts")
            with gr.Row():
                keep_button = gr.Button("🐚 keep this shell in the terrarium",
                                        variant="secondary")
                keep_status = gr.Markdown("")
            recap_output = gr.Markdown(label="slug recap")
            slug_audio = gr.Audio(label="the slug speaks", type="filepath")
            receipt_output = gr.HTML(label="your receipt")
            transcript_output = gr.Markdown(label="transcript")
            raw_json_output = gr.Code(label="Raw JSON", language="json")
            with gr.Row():
                svg_download = gr.File(label="shell.svg")
                receipt_download = gr.File(label="receipt.svg")
                skill_download = gr.File(label="skill.md")
                recap_download = gr.File(label="slug_recap.txt")

        # State holders for the current shell (static SVG + extraction), so the
        # "keep this shell" button can save it to the shared gallery.
        cur_shell_svg = gr.State(None)
        cur_extraction = gr.State(None)

        # Enable the button only once audio is actually present
        audio_input.change(
            fn=on_audio_change,
            inputs=audio_input,
            outputs=[submit_button, status_line],
        )

        # The 12 pipeline outputs (10 UI + 2 state for the gallery save)
        pipeline_outputs = [
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
            cur_shell_svg,
            cur_extraction,
        ]

        def _hide_gifts():
            # On start: hide the gifts, lock the button, set a watching status
            return (
                gr.update(visible=False),
                gr.update(value="🐌 the slug is watching…", interactive=False),
                gr.update(value="*The slug is listening, then it will grow your shell...*"),
            )

        def _reveal_gifts():
            # On finish: reveal the gifts, reset the button
            return (
                gr.update(visible=True),
                gr.update(value="🐌 give it to the slug", interactive=True),
                gr.update(value="*The slug has finished. Your gifts are below.*"),
            )

        # Audio path
        submit_button.click(
            fn=_hide_gifts,
            inputs=None,
            outputs=[gifts_group, submit_button, status_line],
        ).then(
            fn=process_audio,
            inputs=audio_input,
            outputs=pipeline_outputs,
        ).then(
            fn=_reveal_gifts,
            inputs=None,
            outputs=[gifts_group, submit_button, status_line],
        )

        # Trace path
        trace_button.click(
            fn=_hide_gifts,
            inputs=None,
            outputs=[gifts_group, submit_button, status_line],
        ).then(
            fn=process_trace,
            inputs=trace_input,
            outputs=pipeline_outputs,
        ).then(
            fn=_reveal_gifts,
            inputs=None,
            outputs=[gifts_group, submit_button, status_line],
        )

        # ---- Stage B: save the current shell to the shared terrarium ----
        def _keep_shell(svg, extraction):
            if not svg or not extraction:
                return gr.update(value="*No shell to keep yet.*")
            sid = save_shell(svg, extraction)
            if sid:
                return gr.update(
                    value=f"*Kept in the terrarium. Permalink: "
                          f"`?shell={sid}` — share it, or open the gallery tab.*"
                )
            return gr.update(value="*The terrarium was unreachable; shell not saved.*")

        keep_button.click(
            fn=_keep_shell,
            inputs=[cur_shell_svg, cur_extraction],
            outputs=[keep_status],
        )

        # ---- Stage C: the shared gallery (a living terrarium of kept shells) ----
        def _render_gallery():
            shells = list_shells(limit=60)
            if not shells:
                return ("*The terrarium is empty so far. Grow a shell and keep it "
                        "to be the first.*")
            # build a responsive grid of shells; each loads its SVG by id
            cards = []
            for e in shells:
                sid = e.get("id")
                title = e.get("title") or "a session"
                dur = e.get("duration")
                arc = f"{e.get('start','?')} → {e.get('end','?')}"
                sub = f"{dur}m · {arc}" if dur else arc
                data = get_shell(sid) if sid else None
                svg = (data or {}).get("svg", "")
                if not svg:
                    continue
                # shrink each shell into a card via the iframe wrapper (static)
                frame = _wrap_iframe(svg, height=240)
                cards.append(
                    f'<div style="flex:0 0 250px;margin:8px;text-align:center;">'
                    f'<div style="font:600 13px Georgia,serif;color:#c8a24c;">{title}</div>'
                    f'<div style="font:11px monospace;color:#999;margin-bottom:4px;">{sub}</div>'
                    f'{frame}'
                    f'<div style="font:10px monospace;color:#777;">?shell={sid}</div>'
                    f'</div>'
                )
            grid = (
                '<div style="display:flex;flex-wrap:wrap;justify-content:center;">'
                + "".join(cards) + "</div>"
            )
            return grid

        def _load_permalink(request: gr.Request):
            """If the URL has ?shell=<id>, load that single shell on page open."""
            try:
                sid = dict(request.query_params).get("shell")
            except Exception:
                sid = None
            if not sid:
                return gr.update()
            data = get_shell(sid)
            if not data or not data.get("svg"):
                return gr.update(value="*That shell could not be found in the terrarium.*")
            return gr.update(value=_wrap_iframe(data["svg"], height=520))

        with gr.Accordion("🌿 the terrarium (shared gallery)", open=False):
            gr.Markdown(
                "A shared collection of shells people have kept. Each one is the "
                "fingerprint of a real session. Open `?shell=<id>` to link a "
                "specific shell."
            )
            permalink_view = gr.HTML()
            refresh_gallery = gr.Button("↻ refresh the terrarium")
            gallery_grid = gr.HTML()
            refresh_gallery.click(fn=_render_gallery, inputs=None, outputs=[gallery_grid])
            # populate on load + handle ?shell= permalink
            demo.load(fn=_render_gallery, inputs=None, outputs=[gallery_grid])
            demo.load(fn=_load_permalink, inputs=None, outputs=[permalink_view])

    return demo


interface = build_interface()

if __name__ == "__main__":
    interface.launch()
