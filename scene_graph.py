"""
SceneGraph: the deterministic semantic layer of a TurboSkillSlug session.

This is the CONTRACT that every renderer reads. It is built once, deterministically,
from a session extraction, and it is renderer-agnostic. The four lenses (character,
3D shell, generative atmosphere, full diorama) all consume the SAME SceneGraph, so:

  - every visible element still traces to real session data (the core promise),
  - renderers are independent and individually degradable,
  - a new renderer can be added without touching extraction or the others.

Design rules:
  - NOTHING here renders. No SVG, no canvas, no shader. Only structured meaning.
  - Every field is DERIVED from the extraction (or a stable default), so the graph
    is reproducible: same session -> same SceneGraph.
  - Values are normalized and renderer-friendly (0..1 scalars, named enums, hex
    colors) so each renderer can map them without re-interpreting raw extraction.
  - The graph is versioned. Renderers declare which SCHEMA_VERSION they support.
"""

from __future__ import annotations

import colorsys
import hashlib
from dataclasses import dataclass, field, asdict
from typing import Any

SCHEMA_VERSION = "1.0"

# ---- canonical sentiment vocabulary (extraction may use freeform; we map it) ----
# Each sentiment maps to (valence -1..1, energy 0..1) so renderers can blend.
_SENTIMENT_VA = {
    "frustrated": (-0.7, 0.7), "stuck": (-0.6, 0.3), "exhausted": (-0.4, 0.1),
    "anxious": (-0.5, 0.6), "confused": (-0.4, 0.4), "focused": (0.1, 0.6),
    "curious": (0.4, 0.6), "determined": (0.3, 0.7), "calm": (0.3, 0.3),
    "relieved": (0.6, 0.3), "satisfied": (0.7, 0.4), "resolved": (0.7, 0.5),
    "joyful": (0.9, 0.8), "delighted": (0.9, 0.7), "triumphant": (1.0, 0.9),
    "neutral": (0.0, 0.4),
}


def _norm_sentiment(name: str | None) -> str:
    if not name:
        return "neutral"
    n = str(name).strip().lower()
    if n in _SENTIMENT_VA:
        return n
    # nearest by substring, else neutral
    for k in _SENTIMENT_VA:
        if k in n or n in k:
            return k
    return "neutral"


def _va(name: str) -> tuple[float, float]:
    return _SENTIMENT_VA[_norm_sentiment(name)]


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, float(x)))


# ---------------------------------------------------------------------------
# Sub-structures
# ---------------------------------------------------------------------------

@dataclass
class SlugState:
    """How the slug itself looks and feels — for the CHARACTER renderer."""
    mood: str                    # canonical end sentiment
    valence: float               # -1..1  (sad -> happy)
    energy: float                # 0..1   (drained -> lively)
    scars: int                   # = number of dead ends (visible marks on the slug)
    expression: str              # enum: weary|wary|focused|hopeful|elated
    pose: str                    # enum: slumped|neutral|alert|triumphant
    eye_state: str               # enum: heavy|narrow|open|bright


@dataclass
class ShellState:
    """The nautilus geometry parameters — used by ALL renderers (SVG/3D/guide)."""
    turns: float                 # number of spiral revolutions (from duration)
    growth_curve: str            # enum: gentle|steady|steep (pacing of the session)
    knots: list[dict]            # [{t:0..1, severity:0..1}] dead ends along the arm
    jewels: list[dict]           # [{t:0..1}] gotchas along the rim
    aperture: dict               # {t:0..1, intensity:0..1} the breakthrough
    palette: dict                # {start_hex, end_hex, accent_hex}
    iridescence: float           # 0..1 how strongly nacre shifts (for 3D shader)


@dataclass
class ArcState:
    """The emotional timeline — for the SCORE and ATMOSPHERE renderers."""
    start: str
    end: str
    beats: list[dict]            # ordered [{t:0..1, kind, valence, energy, label}]
    tension_curve: list[float]   # sampled 0..1 tension over the session (for music)


@dataclass
class BattleState:
    """The byobu battle cast — for the painted/animated battle layers."""
    general: dict                # {present:bool}
    adversary: dict              # {present:bool, ferocity:0..1}
    fallen: list[dict]           # [{t:0..1}] one per dead end
    archers: list[dict]          # [{t:0..1}] one per gotcha
    dragon: dict                 # {present:bool, t:0..1, scale:0..1} breakthrough


@dataclass
class SceneEnv:
    """The surrounding scene mood — for the BACKDROP/diffusion renderer."""
    time_of_day: str             # dawn|day|dusk|night  (from arc shape)
    weather: str                 # clear|overcast|rain|storm  (from struggle level)
    mood_tags: list[str]         # prompt-ready descriptors for generation
    palette: dict                # {sky_hex, ground_hex, accent_hex}


@dataclass
class SceneGraph:
    schema_version: str
    session_id: str              # stable hash of the extraction (repro + cache key)
    duration_minutes: float
    themes: list[str]
    slug: SlugState
    shell: ShellState
    arc: ArcState
    battle: BattleState
    env: SceneEnv
    # raw escape hatch: renderers that want a field we didn't surface can read this
    extraction: dict = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
