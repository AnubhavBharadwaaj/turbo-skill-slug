"""TurboSkillSlug Gradio application."""

from __future__ import annotations

import gradio as gr


PLACEHOLDER_RESPONSE = "The slug is warming up. Audio analysis will arrive soon."


def process_audio(audio: str | None) -> str:
    """Return a placeholder response for an uploaded or recorded audio file."""
    if audio is None:
        return "Give the slug an audio file first."

    return PLACEHOLDER_RESPONSE


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
        output = gr.Textbox(label="Slug response")

        submit_button.click(
            fn=process_audio,
            inputs=audio_input,
            outputs=output,
        )

    return demo


interface = build_interface()


if __name__ == "__main__":
    interface.launch()
