"""TurboSkillSlug Gradio application."""

from __future__ import annotations

import gradio as gr

from transcribe import transcribe_audio


def process_audio(audio: str | None) -> str:
    """Transcribe an uploaded or recorded audio file."""
    if audio is None:
        return "Give the slug an audio file first."

    transcript = transcribe_audio(audio)
    return f"## Transcript\n\n{transcript}"


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
        output = gr.Markdown()

        submit_button.click(
            fn=process_audio,
            inputs=audio_input,
            outputs=output,
        )

    return demo


interface = build_interface()


if __name__ == "__main__":
    interface.launch()
