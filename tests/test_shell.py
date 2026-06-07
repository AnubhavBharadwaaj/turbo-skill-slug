"""Tests for SVG shell generation."""

from __future__ import annotations

from typing import Any

from shell import generate_shell_svg


def _sample_features() -> dict[str, Any]:
    """Return representative extracted session features."""
    return {
        "duration_minutes": 47,
        "themes": ["debug", "build"],
        "approaches_tried": [
            {"approach": "naive regex", "outcome": "too brittle"},
            {"approach": "parser pass", "outcome": "worked"},
        ],
        "dead_ends": [
            {"position": 0.2, "what_happened": "regex backtracked"},
            {"position": 0.45, "what_happened": "missed a nested case"},
        ],
        "breakthroughs": [{"position": 0.88, "what_worked": "walked the tree"}],
        "gotchas": ["line endings", "unicode names"],
        "sentiment_arc": {"start": "frustrated", "end": "resolved"},
        "skill_md": "# Skill\n\nUse the session.",
        "slug_voice": ["A small clue held still."],
    }


def test_generate_shell_svg_contains_expected_elements() -> None:
    """The shell SVG includes core visual markers for mapped session features."""
    svg = generate_shell_svg(_sample_features())

    assert svg.startswith('<svg xmlns="http://www.w3.org/2000/svg"')
    assert 'class="shell-body"' in svg
    assert 'class="dead-end-knot"' in svg
    assert 'class="gotcha-jewel"' in svg
    assert 'class="breakthrough-aperture"' in svg
    assert 'id="bodyGrad"' in svg
