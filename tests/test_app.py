"""Smoke tests for the TurboSkillSlug app."""

from __future__ import annotations

import importlib

import gradio as gr


def test_interface_exists() -> None:
    """The app module exposes a Gradio Blocks interface."""
    app = importlib.import_module("app")

    assert hasattr(app, "interface")
    assert isinstance(app.interface, gr.Blocks)
