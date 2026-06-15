"""TurboSkillSlug Gradio application."""

from __future__ import annotations

import base64 as b64lib
import html
import json
import os
import shutil
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
from shell_animate import wrap_in_iframe, animate_shell_svg
from shell_unroll import build_unroll_doc, N_STAGES
from gallery_client import save_shell, list_shells, get_shell
from battle_trace import render_battle_trace
from shell3d_lens import render_shell_3d
from shell_animate import wrap_in_iframe as _wrap_iframe
from transcribe import transcribe_audio
from trace_parser import parse_trace_to_transcript, detect_trace_format
from model_guard import APP_RUNTIME

# REQ-01 guard: mark this process as the live app. From here on, any attempt to
# call an over-32B model (via assert_small_model) will raise instead of shipping
# a compliance violation. Offline eval/research scripts never enable this flag.
APP_RUNTIME.enable()


# Growth stages for the live shell reveal. The slug grows the shell as it
# watches: spiral lengthens, knots and jewels form in order, aperture opens last.
GROWTH_STAGES = [0.18, 0.38, 0.58, 0.78, 1.0]
GROWTH_PACING_SECONDS = 0.55  # brief pause between stages so the eye sees growth

TTS_URL = os.environ.get(
    "MODAL_TTS_URL",
    "https://anubhavbharadwaaj--slugvoice-tts-slugtts-api.modal.run",
)
SAMPLE_WAV_NAME = "sample_session.wav"
SAMPLE_WAV_PATH = Path(__file__).parent / SAMPLE_WAV_NAME


def _resolve_audio_path(audio: str | None) -> str | None:
    """Return a readable audio path for the pipeline.

    Gradio example uploads can point at evictable temp files on HF Spaces. If the
    one-click sample's temp copy is gone, recover from the committed repo copy
    by copying it to a fresh temp file owned by this request.
    """
    if audio and os.path.exists(audio):
        return audio

    looks_like_sample = audio and SAMPLE_WAV_NAME in os.path.basename(audio)
    if (looks_like_sample or audio is None) and SAMPLE_WAV_PATH.exists():
        dst = Path(tempfile.mkdtemp(prefix="slug_sample_")) / SAMPLE_WAV_NAME
        shutil.copy(SAMPLE_WAV_PATH, dst)
        print(f"[SAMPLE] recovered evicted sample from committed repo copy: {dst}")
        return str(dst)

    return audio


def _base_url_from_request(request) -> str:
    """Reconstruct the app's public base URL (with trailing /) from a gr.Request.

    On HF Spaces the app sits behind a reverse proxy, so the real public host is
    in x-forwarded-host (not request.url's internal host). We prefer the
    forwarded headers and fall back to request.headers['host'] / request.url.
    """
    try:
        headers = {k.lower(): v for k, v in dict(request.headers).items()}
    except Exception:
        headers = {}
    host = headers.get("x-forwarded-host") or headers.get("host")
    proto = headers.get("x-forwarded-proto") or "https"
    if host:
        return f"{proto}://{host}/"
    # last-resort fallback to the request URL's origin
    try:
        u = str(request.url)
        # strip any path/query
        from urllib.parse import urlparse
        p = urlparse(u)
        if p.scheme and p.netloc:
            return f"{p.scheme}://{p.netloc}/"
    except Exception:
        pass
    return "/"


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


def _format_shell_legend(extraction: dict[str, Any]) -> str:
    """Return a compact genre-aware legend for the shell display."""
    genre = str(extraction.get("genre") or "session")
    legend = extraction.get("shell_legend") or {}
    if not isinstance(legend, dict) or not legend:
        return ""

    knot = html.escape(str(legend.get("knot", "dead ends")))
    jewel = html.escape(str(legend.get("jewel", "gotchas")))
    aperture = html.escape(str(legend.get("aperture", "breakthrough")))
    genre_label = html.escape(genre.replace("_", " "))
    return (
        '<div style="font: 13px system-ui, sans-serif; '
        'color: #4d4637 !important; background: #fff8e8 !important; '
        'border: 1px solid #c8a24c; border-radius: 8px; '
        'padding: 10px 12px; margin: 8px 0 12px;">'
        f'<strong>Shell legend ({genre_label})</strong>: knots = {knot}; '
        f'jewels = {jewel}; aperture = {aperture}.'
        "</div>"
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
    shell_display = _format_shell_legend(extraction) + shell_display
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
    audio = _resolve_audio_path(audio)
    if audio is None or not os.path.exists(audio):
        yield _empty_outputs(
            "The slug couldn't find that audio file. On HF Spaces an upload can "
            "expire; please re-upload and try again."
        )
        return

    try:
        transcript = transcribe_audio(audio)
        extraction = extract_session(transcript)
    except Exception as e:
        print(f"[PIPELINE] audio path failed: {type(e).__name__}: {e}")
        yield _empty_outputs(
            "The slug couldn't read this session right now — the extractor is "
            "temporarily unavailable. Please try again, or use the trace tab."
        )
        return
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
                            examples=[str(SAMPLE_WAV_PATH)],
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

        # State holders for the current shell (static SVG + extraction), used by
        # the "keep this shell" gallery save and the experimental battle replay.
        cur_shell_svg = gr.State(None)
        cur_extraction = gr.State(None)

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

            # Experimental: the LITERAL temporal replay of the session as a war
            # between you (the Agent) and the Environment. The shell remembers
            # the campaign as a frozen folding screen; this replays it in time.
            with gr.Accordion("⚔ the battle, as it happened (replay)", open=False):
                gr.Markdown(
                    "The shell is how the slug *remembers* the battle: the "
                    "aftermath, frozen like a folding screen, where the dead "
                    "ends fell and where the breakthrough struck. This is the "
                    "*replay* of that same battle as it actually happened in "
                    "time, your moves against the Environment's strikes (dead "
                    "ends), the clashes (gotchas), and the blow that finally "
                    "lands (the breakthrough). Memory above; footage here."
                )
                battle_view = gr.HTML()
                battle_button = gr.Button("⚔ replay the battle the slug remembers")

                def _show_battle(extraction):
                    if not extraction:
                        return gr.update(value="*The slug has no battle to replay yet.*")
                    return gr.update(value=render_battle_trace(extraction, height=440))

                battle_button.click(
                    fn=_show_battle,
                    inputs=[cur_extraction],
                    outputs=[battle_view],
                )

            # The shell as a real 3D object you can turn in the light. Same session
            # data, a different lens: the SceneGraph drives a Three.js nautilus with
            # iridescent nacre. First of the planned multi-lens renderers.
            with gr.Accordion("🔮 turn the shell in 3D (experimental lens)", open=False):
                gr.Markdown(
                    "The same shell, rendered as a real object you can orbit. The "
                    "spiral's growth, the knots (dead ends), the glowing aperture "
                    "(breakthrough), and the colour arc all come from your session, "
                    "now with true iridescent nacre. Drag to turn it; scroll to zoom."
                )
                shell3d_view = gr.HTML()
                shell3d_button = gr.Button("🔮 see this shell in 3D")

                def _show_shell3d(extraction):
                    if not extraction:
                        return gr.update(value="*No shell to render in 3D yet.*")
                    html = render_shell_3d(extraction)
                    if not html:
                        return gr.update(value="*The 3D lens is unavailable right now.*")
                    return gr.update(value=html)

                shell3d_button.click(
                    fn=_show_shell3d,
                    inputs=[cur_extraction],
                    outputs=[shell3d_view],
                )

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
        def _keep_shell(svg, extraction, request: gr.Request):
            if not svg or not extraction:
                return gr.update(value="*No shell to keep yet.*")
            sid = save_shell(svg, extraction)
            if not sid:
                return gr.update(value="*The terrarium was unreachable; shell not saved.*")
            # Build a COMPLETE clickable link (not a bare ?shell= fragment, which
            # is confusing). Derive the base URL from the request's headers.
            base = _base_url_from_request(request)
            link = f"{base}?shell={sid}"
            return gr.update(
                value=(
                    f"🐚 **Kept in the terrarium.** Here's the shareable link to "
                    f"this exact shell:\n\n[{link}]({link})\n\n"
                    f"_Anyone who opens it sees this shell unroll. You can also "
                    f"browse all kept shells in the terrarium below._"
                )
            )

        keep_button.click(
            fn=_keep_shell,
            inputs=[cur_shell_svg, cur_extraction],
            outputs=[keep_status],
        )

        # ---- Stage C: the shared gallery (a living terrarium of kept shells) ----
        def _render_gallery(request: gr.Request):
            shells = list_shells(limit=60)
            if not shells:
                return ("*The terrarium is empty so far. Grow a shell and keep it "
                        "to be the first.*")
            base = _base_url_from_request(request)
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
                # shrink each shell into a card; static, no replay button (these
                # are kept shells, like photos in an album — the replay belongs
                # to the focused permalink view below).
                frame = _wrap_iframe(svg, height=240, replay=False)
                link = f"{base}?shell={sid}"
                cards.append(
                    f'<div style="flex:0 0 250px;margin:8px;text-align:center;">'
                    f'<div style="font:600 13px Georgia,serif;color:#c8a24c;">{title}</div>'
                    f'<div style="font:11px monospace;color:#999;margin-bottom:4px;">{sub}</div>'
                    f'{frame}'
                    f'<div style="margin-top:4px;"><a href="{link}" target="_blank" '
                    f'style="font:12px Georgia,serif;color:#6ee7ff;text-decoration:none;">'
                    f'open this shell →</a></div>'
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
            # Re-animate the saved static shell for the focused permalink view:
            # the mask-based scroll-unroll works on a single SVG (no growth
            # stages needed), so this shell unrolls and the replay button works.
            try:
                animated = animate_shell_svg(data["svg"])
                return gr.update(value=wrap_in_iframe(animated, height=520, replay=True))
            except Exception:
                return gr.update(value=_wrap_iframe(data["svg"], height=520, replay=False))

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
