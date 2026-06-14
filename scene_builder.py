"""
build_scene_graph(extraction) -> SceneGraph

Deterministically derives the full semantic scene from a session extraction. Every
field traces to real data; same extraction always yields the same graph. This is
the ONLY place extraction-shape knowledge lives — renderers never touch raw
extraction (except via the escape hatch).
"""

from __future__ import annotations

import colorsys
import hashlib
import json

from scene_graph import (
    SceneGraph, SlugState, ShellState, ArcState, BattleState, SceneEnv,
    SCHEMA_VERSION, _norm_sentiment, _va, _clamp01,
)


def _session_id(extraction: dict) -> str:
    blob = json.dumps(extraction, sort_keys=True, default=str).encode()
    return hashlib.sha256(blob).hexdigest()[:16]


def _hex_from_va(valence: float, energy: float) -> str:
    """Map valence/energy to a hue/sat/light color. Negative=cool, positive=warm."""
    # hue: 0.0 (red) .. 0.33 (green) .. 0.58 (blue). Warm/positive -> gold-green,
    # cool/negative -> blue. Map valence -1..1 to hue 0.58..0.13.
    hue = 0.58 - (valence + 1) / 2 * 0.45
    sat = 0.35 + energy * 0.4
    light = 0.42 + (valence + 1) / 2 * 0.18
    r, g, b = colorsys.hls_to_rgb(hue, light, sat)
    return f"#{int(r*255):02x}{int(g*255):02x}{int(b*255):02x}"


def _build_slug(end_sent: str, dead_ends: list, arc_end_va) -> SlugState:
    val, en = arc_end_va
    scars = len(dead_ends)
    # expression/pose/eyes derived from valence+energy bands
    if val >= 0.6:
        expr, pose, eye = "elated", "triumphant", "bright"
    elif val >= 0.2:
        expr, pose, eye = "hopeful", "alert", "open"
    elif val >= -0.2:
        expr, pose, eye = "focused", "neutral", "narrow"
    elif en <= 0.25:
        expr, pose, eye = "weary", "slumped", "heavy"
    else:
        expr, pose, eye = "wary", "neutral", "narrow"
    return SlugState(
        mood=_norm_sentiment(end_sent), valence=round(val, 3), energy=round(en, 3),
        scars=scars, expression=expr, pose=pose, eye_state=eye,
    )


def _build_shell(duration, approaches, dead_ends, gotchas, breakthroughs,
                 start_va, end_va) -> ShellState:
    turns = max(1.0, min(6.0, (duration or 30) / 30.0))  # ~1 turn per 30 min, cap 6
    n = len(approaches) + len(dead_ends)
    growth_curve = "gentle" if n <= 2 else ("steady" if n <= 5 else "steep")
    knots = [{"t": _clamp01(float(d.get("position", 0.5))),
              "severity": 0.5} for d in dead_ends if isinstance(d, dict)]
    jewels = [{"t": _clamp01((i + 1) / (len(gotchas) + 1))}
              for i in range(len(gotchas))]
    if breakthroughs:
        b = breakthroughs[-1]
        ap_t = _clamp01(float(b.get("position", 0.9))) if isinstance(b, dict) else 0.9
    else:
        ap_t = 0.9
    palette = {
        "start_hex": _hex_from_va(*start_va),
        "end_hex": _hex_from_va(*end_va),
        "accent_hex": "#e6c870",
    }
    # iridescence stronger when the arc swings far (struggle -> triumph reads richer)
    swing = abs(end_va[0] - start_va[0])
    return ShellState(
        turns=round(turns, 2), growth_curve=growth_curve, knots=knots, jewels=jewels,
        aperture={"t": ap_t, "intensity": round(0.6 + 0.4 * swing / 2, 3)},
        palette=palette, iridescence=round(_clamp01(0.4 + swing / 2), 3),
    )


def _build_arc(start_sent, end_sent, dead_ends, breakthroughs, gotchas) -> ArcState:
    beats = []
    for d in dead_ends:
        if isinstance(d, dict):
            t = _clamp01(float(d.get("position", 0.5)))
            v, e = -0.6, 0.4
            beats.append({"t": t, "kind": "dead_end", "valence": v, "energy": e,
                          "label": str(d.get("what_happened", "a wall"))[:60]})
    for i, g in enumerate(gotchas):
        beats.append({"t": _clamp01(0.3 + i * 0.1), "kind": "gotcha",
                      "valence": -0.3, "energy": 0.5, "label": str(g)[:60]})
    for b in breakthroughs:
        if isinstance(b, dict):
            t = _clamp01(float(b.get("position", 0.9)))
            beats.append({"t": t, "kind": "breakthrough", "valence": 0.8, "energy": 0.8,
                          "label": str(b.get("what_worked", "it gave way"))[:60]})
    beats.sort(key=lambda x: x["t"])
    # sample a tension curve (0..1) across 16 points: high during dead-end clusters,
    # dropping at the breakthrough. Simple kernel sum.
    samples = []
    for k in range(16):
        t = k / 15
        tension = 0.2
        for be in beats:
            d = abs(be["t"] - t)
            w = max(0.0, 1 - d * 6)
            if be["kind"] in ("dead_end", "gotcha"):
                tension += 0.6 * w
            elif be["kind"] == "breakthrough":
                tension -= 0.5 * w
        samples.append(round(_clamp01(tension), 3))
    return ArcState(start=_norm_sentiment(start_sent), end=_norm_sentiment(end_sent),
                    beats=beats, tension_curve=samples)


def _build_battle(approaches, dead_ends, gotchas, breakthroughs) -> BattleState:
    ferocity = _clamp01(0.3 + 0.15 * len(dead_ends))
    fallen = [{"t": _clamp01(float(d.get("position", 0.5)))}
              for d in dead_ends if isinstance(d, dict)]
    archers = [{"t": _clamp01(0.5 + i * 0.08)} for i in range(len(gotchas))]
    if breakthroughs:
        b = breakthroughs[-1]
        dragon = {"present": True,
                  "t": _clamp01(float(b.get("position", 0.9))) if isinstance(b, dict) else 0.9,
                  "scale": _clamp01(0.7 + 0.3 * min(1, len(breakthroughs)))}
    else:
        dragon = {"present": False, "t": 1.0, "scale": 0.0}
    return BattleState(
        general={"present": bool(approaches)},
        adversary={"present": True, "ferocity": round(ferocity, 3)},
        fallen=fallen, archers=archers, dragon=dragon,
    )


def _build_env(start_va, end_va, dead_ends, themes) -> SceneEnv:
    # time of day from the arc's emotional journey
    sv, ev = start_va[0], end_va[0]
    if ev >= 0.5 and sv < 0:
        tod = "dawn"        # struggle -> triumph reads as a sunrise
    elif ev >= 0.4:
        tod = "day"
    elif ev <= -0.3:
        tod = "night"
    else:
        tod = "dusk"
    # weather from struggle density
    struggle = len(dead_ends)
    weather = "clear" if struggle <= 1 else ("overcast" if struggle <= 3 else
              ("rain" if struggle <= 5 else "storm"))
    mood_tags = []
    mood_tags.append({"dawn": "first light, hopeful", "day": "bright, open",
                      "dusk": "golden hour, reflective", "night": "deep blue, quiet"}[tod])
    mood_tags.append({"clear": "still air", "overcast": "soft grey sky",
                      "rain": "gentle rain", "storm": "dramatic storm"}[weather])
    if themes:
        mood_tags.append(f"a sense of {themes[0]}")
    palette = {
        "sky_hex": _hex_from_va(*end_va),
        "ground_hex": "#1a1410",
        "accent_hex": "#e6c870",
    }
    return SceneEnv(time_of_day=tod, weather=weather, mood_tags=mood_tags, palette=palette)


def build_scene_graph(extraction: dict) -> SceneGraph:
    ex = extraction or {}
    themes = ex.get("themes") or []
    approaches = ex.get("approaches_tried") or []
    dead_ends = ex.get("dead_ends") or []
    gotchas = ex.get("gotchas") or []
    breakthroughs = ex.get("breakthroughs") or []
    arc = ex.get("sentiment_arc") or {}
    start_sent, end_sent = arc.get("start"), arc.get("end")
    duration = ex.get("duration_minutes")

    start_va, end_va = _va(start_sent), _va(end_sent)

    return SceneGraph(
        schema_version=SCHEMA_VERSION,
        session_id=_session_id(ex),
        duration_minutes=float(duration or 0),
        themes=themes,
        slug=_build_slug(end_sent, dead_ends, end_va),
        shell=_build_shell(duration, approaches, dead_ends, gotchas, breakthroughs, start_va, end_va),
        arc=_build_arc(start_sent, end_sent, dead_ends, breakthroughs, gotchas),
        battle=_build_battle(approaches, dead_ends, gotchas, breakthroughs),
        env=_build_env(start_va, end_va, dead_ends, themes),
        extraction=ex,
    )
