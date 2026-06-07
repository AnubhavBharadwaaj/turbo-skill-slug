"""SVG shell generation for TurboSkillSlug sessions.

The shell maps extraction features to a nautilus-inspired SVG:

- duration controls the spiral size
- approaches tried control the spiral density
- dead ends appear as dark knots on the spiral body
- breakthroughs mark the aperture at the spiral tip
- gotchas become iridescent jewels along the rim
- the sentiment arc drives a start-to-end color gradient
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import Any


SENTIMENT_COLORS: dict[str, str] = {
    "confused": "#5b4a7a",
    "focused": "#2a4a6e",
    "frustrated": "#7a2f2f",
    "curious": "#3b6e6e",
    "resolved": "#5a8c6f",
    "joyful": "#c79a3a",
    "exhausted": "#8a8a9a",
    "enlightened": "#d4b97a",
}
DEFAULT_START = "#5b4a7a"
DEFAULT_END = "#c79a3a"
SVG_SIZE = 640

SpiralPoint = tuple[float, float, float, float, float]


def _as_sequence(value: Any) -> Sequence[Any]:
    """Return list-like feature values, falling back to an empty tuple."""
    return value if isinstance(value, Sequence) and not isinstance(value, str) else ()


def _as_mapping(value: Any) -> Mapping[str, Any]:
    """Return dict-like feature values, falling back to an empty mapping."""
    return value if isinstance(value, Mapping) else {}


def _clamp(value: float, minimum: float, maximum: float) -> float:
    """Clamp a float to the inclusive range provided."""
    return max(minimum, min(maximum, value))


def _color(name: Any, fallback: str) -> str:
    """Map a sentiment name to a color, using fallback for unknown names."""
    key = str(name or "").lower().strip()
    return SENTIMENT_COLORS.get(key, fallback)


def _float_feature(value: Any, fallback: float) -> float:
    """Convert a feature value to float without letting malformed data leak out."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return fallback


def _int_feature(value: Any, fallback: int) -> int:
    """Convert a feature value to int without letting malformed data leak out."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return fallback


def _log_spiral(
    cx: float,
    cy: float,
    n_turns: float,
    r0: float,
    r_max: float,
    n_points: int = 480,
) -> list[SpiralPoint]:
    """Return points along a logarithmic spiral.

    Each point is ``(x, y, theta, radius, normal_angle)`` so downstream drawing
    code can derive rim positions and cross-body ridges without recomputing
    spiral geometry.
    """
    turns = max(n_turns, 1.5)
    t_max = 2 * math.pi * turns
    b = math.log(max(r_max, r0 + 1) / r0) / t_max
    points: list[SpiralPoint] = []

    for i in range(n_points):
        t = (i / (n_points - 1)) * t_max
        r = r0 * math.exp(b * t)
        x = cx + r * math.cos(t)
        y = cy + r * math.sin(t)
        tangent = t + math.atan2(1, b) if b > 0 else t + math.pi / 2
        normal = tangent + math.pi / 2
        points.append((x, y, t, r, normal))

    return points


def _band_path(inner: Sequence[SpiralPoint], outer: Sequence[SpiralPoint]) -> str:
    """Return a closed SVG path that follows the outer rim and inner rim."""
    if not inner or not outer:
        return ""

    parts = [f"M {outer[0][0]:.2f} {outer[0][1]:.2f}"]
    parts.extend(f"L {x:.2f} {y:.2f}" for x, y, *_ in outer[1:])
    parts.extend(f"L {x:.2f} {y:.2f}" for x, y, *_ in reversed(inner))
    parts.append("Z")
    return " ".join(parts)


def _stroke_path(points: Sequence[SpiralPoint]) -> str:
    """Return an open SVG path through the supplied spiral points."""
    if not points:
        return ""

    head = f"M {points[0][0]:.2f} {points[0][1]:.2f}"
    tail = " ".join(f"L {x:.2f} {y:.2f}" for x, y, *_ in points[1:])
    return f"{head} {tail}"


def generate_shell_svg(features: dict[str, Any]) -> str:
    """Generate a unique SVG shell from extracted session features."""
    duration = int(_clamp(_int_feature(features.get("duration_minutes"), 30), 5, 180))
    approaches = _as_sequence(features.get("approaches_tried"))
    dead_ends = _as_sequence(features.get("dead_ends"))
    breakthroughs = _as_sequence(features.get("breakthroughs"))
    gotchas = _as_sequence(features.get("gotchas"))
    themes = set(_as_sequence(features.get("themes")))
    sentiment = _as_mapping(features.get("sentiment_arc"))

    start_color = _color(sentiment.get("start"), DEFAULT_START)
    end_color = _color(sentiment.get("end"), DEFAULT_END)

    width = height = SVG_SIZE
    cx = width / 2
    cy = height / 2 + 20

    breakthrough = _as_mapping(breakthroughs[-1]) if breakthroughs else {}
    aperture_pos = _clamp(_float_feature(breakthrough.get("position"), 0.97), 0.6, 0.99)

    ideal_turns = min(2.4 + 0.35 * len(approaches) + duration / 150.0, 4.5)
    n_turns = ideal_turns * aperture_pos
    r0 = 5.0
    r_max = min(width * 0.40, 70 + duration * 2.2)
    centerline = _log_spiral(cx, cy, n_turns, r0, r_max)

    def thickness_at(idx: int, total: int) -> float:
        """Return shell body thickness for a point index along the spiral."""
        frac = idx / max(1, total - 1)
        return 3 + (r_max * 0.30) * (frac**1.4)

    outer_points: list[SpiralPoint] = []
    inner_points: list[SpiralPoint] = []
    for i, (x, y, theta, radius, normal) in enumerate(centerline):
        thickness = thickness_at(i, len(centerline))
        outer_points.append(
            (
                x + math.cos(normal) * thickness,
                y + math.sin(normal) * thickness,
                theta,
                radius,
                normal,
            )
        )
        inner_points.append(
            (
                x - math.cos(normal) * thickness,
                y - math.sin(normal) * thickness,
                theta,
                radius,
                normal,
            )
        )

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
        f'width="{width}" height="{height}" font-family="Georgia, serif" '
        'role="img" aria-labelledby="shell-title shell-desc">',
        "<title id=\"shell-title\">TurboSkillSlug session shell</title>",
        (
            '<desc id="shell-desc">A nautilus-inspired recap shell generated from '
            "session duration, attempts, dead ends, breakthroughs, gotchas, and "
            "sentiment.</desc>"
        ),
        f"""
    <defs>
      <linearGradient id="bodyGrad" x1="0%" y1="0%" x2="100%" y2="100%">
        <stop offset="0%" stop-color="{start_color}"/>
        <stop offset="100%" stop-color="{end_color}"/>
      </linearGradient>
      <radialGradient id="aperture" cx="50%" cy="50%" r="60%">
        <stop offset="0%" stop-color="#fff3d6" stop-opacity="0.95"/>
        <stop offset="60%" stop-color="{end_color}" stop-opacity="0.5"/>
        <stop offset="100%" stop-color="{end_color}" stop-opacity="0"/>
      </radialGradient>
      <radialGradient id="jewel" cx="35%" cy="35%" r="65%">
        <stop offset="0%" stop-color="#fff" stop-opacity="0.95"/>
        <stop offset="50%" stop-color="{end_color}" stop-opacity="0.8"/>
        <stop offset="100%" stop-color="#1a0e22" stop-opacity="0.4"/>
      </radialGradient>
    </defs>
    """,
    ]

    parts.append(f'<rect width="{width}" height="{height}" fill="#0d0a16"/>')
    parts.append(f'<circle cx="{cx}" cy="{cy}" r="{r_max + 100}" fill="{start_color}" opacity="0.06"/>')
    parts.append(f'<circle cx="{cx}" cy="{cy}" r="{r_max + 50}" fill="{end_color}" opacity="0.05"/>')
    parts.append(
        f'<path class="shell-body" d="{_band_path(inner_points, outer_points)}" '
        'fill="url(#bodyGrad)" stroke="#2a1f3a" stroke-width="0.8"/>'
    )

    septa_step = 16 if "debug" in themes else (20 if "build" in themes else 18)
    for i in range(septa_step, len(centerline) - 5, septa_step):
        ix, iy = inner_points[i][0], inner_points[i][1]
        ox, oy = outer_points[i][0], outer_points[i][1]
        parts.append(
            f'<line class="shell-septa" x1="{ix:.2f}" y1="{iy:.2f}" '
            f'x2="{ox:.2f}" y2="{oy:.2f}" stroke="#1a0e22" '
            'stroke-width="0.9" opacity="0.55"/>'
        )

    for frac, opacity in [(0.25, 0.35), (0.5, 0.45), (0.75, 0.35)]:
        band = []
        for (ox, oy, *_), (ix, iy, *_) in zip(outer_points, inner_points, strict=True):
            band.append((ix + (ox - ix) * frac, iy + (oy - iy) * frac))
        path_d = "M " + " L ".join(f"{x:.2f} {y:.2f}" for x, y in band)
        color = end_color if frac > 0.5 else start_color
        parts.append(
            f'<path class="shell-band" d="{path_d}" fill="none" stroke="{color}" '
            f'stroke-width="0.8" opacity="{opacity}"/>'
        )

    parts.append(
        f'<path class="shell-highlight" d="{_stroke_path(centerline)}" fill="none" '
        'stroke="#f5e8c8" stroke-width="0.6" opacity="0.55"/>'
    )

    for dead_end in dead_ends:
        dead_end_map = _as_mapping(dead_end)
        pos = _clamp(_float_feature(dead_end_map.get("position"), 0.5), 0.03, 0.97)
        idx = int(pos * (len(centerline) - 1))
        x, y, _, _, _ = centerline[idx]
        thickness = thickness_at(idx, len(centerline))
        parts.append(
            f'<circle class="dead-end-knot" cx="{x:.2f}" cy="{y:.2f}" '
            f'r="{max(3.5, thickness * 0.35):.2f}" fill="#0e0719" '
            f'stroke="{start_color}" stroke-width="1.2" opacity="0.95"/>'
        )
        parts.append(
            f'<circle class="dead-end-glint" cx="{x - 1:.2f}" cy="{y - 1:.2f}" '
            f'r="1.1" fill="{start_color}" opacity="0.7"/>'
        )

    n_jewels = min(len(gotchas), 14)
    for i in range(n_jewels):
        frac = 0.30 + (i / max(1, n_jewels)) * 0.65
        idx = int(frac * (len(outer_points) - 1))
        ox, oy, _, _, normal = outer_points[idx]
        jx = ox + math.cos(normal) * 3.5
        jy = oy + math.sin(normal) * 3.5
        parts.append(
            f'<circle class="gotcha-jewel" cx="{jx:.2f}" cy="{jy:.2f}" r="4.5" '
            'fill="url(#jewel)" opacity="0.95" stroke="#fff7e0" '
            'stroke-width="0.4" stroke-opacity="0.5"/>'
        )

    aperture_idx = len(centerline) - 1
    bx, by, _, _, bn = centerline[aperture_idx]
    bth = thickness_at(aperture_idx, len(centerline))
    rotation = math.degrees(bn)
    parts.append(
        f'<ellipse class="breakthrough-aperture" cx="{bx:.2f}" cy="{by:.2f}" '
        f'rx="{bth * 1.25:.2f}" ry="{bth * 0.95:.2f}" '
        f'transform="rotate({rotation:.1f} {bx:.2f} {by:.2f})" '
        'fill="url(#aperture)" opacity="0.95"/>'
    )
    parts.append(
        f'<ellipse class="breakthrough-glow" cx="{bx:.2f}" cy="{by:.2f}" '
        f'rx="{bth * 0.45:.2f}" ry="{bth * 0.30:.2f}" '
        f'transform="rotate({rotation:.1f} {bx:.2f} {by:.2f})" '
        'fill="#fff7e0" opacity="0.85"/>'
    )

    parts.append(
        f'<text x="{width - 14}" y="{height - 14}" text-anchor="end" '
        'fill="#7a6f96" font-size="10" opacity="0.65" font-style="italic">'
        f"turboskillslug | {duration}m | {len(approaches)} tried | "
        f"{len(dead_ends)} stumbles | {len(gotchas)} jewels</text>"
    )
    parts.append("</svg>")

    return "\n".join(parts)
