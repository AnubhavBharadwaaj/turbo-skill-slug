"""
Shell generator. Every shell is unique because every session is unique.
Pure-Python SVG via string templates — no extra deps, easy to tune.

Visual anatomy (nautilus-inspired):
  - thick spiral *body* (filled band between two parallel log-spirals)
  - septa: ridges across the body at regular chamber intervals
  - longitudinal bands: color stripes running along the spiral
  - dead-end knots: dark inclusions ON the body at fractional positions
  - gotcha jewels: small iridescent dots along the outer rim
  - aperture: an opening at the end of the spiral (the breakthrough)
  - sentiment gradient: colors mapped from start->end of session
"""

import math

SENTIMENT_COLORS = {
    "confused":    "#5b4a7a",
    "focused":     "#2a4a6e",
    "frustrated":  "#7a2f2f",
    "curious":     "#3b6e6e",
    "resolved":    "#5a8c6f",
    "joyful":      "#c79a3a",
    "exhausted":   "#8a8a9a",
    "enlightened": "#d4b97a",
}

DEFAULT_START = "#5b4a7a"
DEFAULT_END = "#c79a3a"


def _color(name, fallback):
    return SENTIMENT_COLORS.get((name or "").lower().strip(), fallback)


def _log_spiral(cx, cy, n_turns, r0, r_max, n_points=480):
    """Points along a log spiral. Returns (x, y, theta, r, normal_angle)."""
    if n_turns <= 0:
        n_turns = 1.5
    t_max = 2 * math.pi * n_turns
    b = math.log(max(r_max, r0 + 1) / r0) / t_max
    pts = []
    for i in range(n_points):
        t = (i / (n_points - 1)) * t_max
        r = r0 * math.exp(b * t)
        x = cx + r * math.cos(t)
        y = cy + r * math.sin(t)
        # tangent angle of log spiral, then outward normal
        tangent = t + math.atan2(1, b) if b > 0 else t + math.pi / 2
        normal = tangent + math.pi / 2
        pts.append((x, y, t, r, normal))
    return pts


def _band_path(inner, outer):
    """Closed SVG path going along outer then back along inner."""
    if not inner or not outer:
        return ""
    parts = [f"M {outer[0][0]:.2f} {outer[0][1]:.2f}"]
    for x, y, *_ in outer[1:]:
        parts.append(f"L {x:.2f} {y:.2f}")
    for x, y, *_ in reversed(inner):
        parts.append(f"L {x:.2f} {y:.2f}")
    parts.append("Z")
    return " ".join(parts)


def _stroke_path(pts):
    if not pts:
        return ""
    head = f"M {pts[0][0]:.2f} {pts[0][1]:.2f}"
    return head + " " + " ".join(f"L {x:.2f} {y:.2f}" for x, y, *_ in pts[1:])


def generate_shell_svg(features: dict) -> str:
    duration = max(5, min(180, int(features.get("duration_minutes", 30) or 30)))
    approaches = features.get("approaches_tried", []) or []
    dead_ends = features.get("dead_ends", []) or []
    breakthroughs = features.get("breakthroughs", []) or []
    gotchas = features.get("gotchas", []) or []
    themes = features.get("themes", []) or []
    sentiment = features.get("sentiment_arc", {}) or {}

    start_color = _color(sentiment.get("start"), DEFAULT_START)
    end_color = _color(sentiment.get("end"), DEFAULT_END)

    W = H = 640
    cx, cy = W / 2, H / 2 + 20

    # Aperture (mouth) is the breakthrough; the spiral ENDS there.
    if breakthroughs:
        aperture_pos = max(0.6, min(0.99, float(breakthroughs[-1].get("position", 0.97))))
    else:
        aperture_pos = 0.97

    # We design the spiral so that aperture_pos is at the end of the spiral.
    # Total ideal n_turns the session deserves, then we trim to the aperture.
    ideal_turns = 2.4 + 0.35 * len(approaches) + duration / 150.0
    ideal_turns = min(ideal_turns, 4.5)
    n_turns = ideal_turns * aperture_pos
    r0 = 5
    r_max = min(W * 0.40, 70 + duration * 2.2)

    centerline = _log_spiral(cx, cy, n_turns, r0, r_max, n_points=480)

    def thickness_at(idx, total):
        frac = idx / max(1, total - 1)
        return 3 + (r_max * 0.30) * (frac ** 1.4)

    outer_pts, inner_pts = [], []
    for i, (x, y, t, r, n) in enumerate(centerline):
        th = thickness_at(i, len(centerline))
        outer_pts.append((x + math.cos(n) * th, y + math.sin(n) * th, t, r, n))
        inner_pts.append((x - math.cos(n) * th, y - math.sin(n) * th, t, r, n))

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" '
        f'width="{W}" height="{H}" font-family="Georgia, serif">'
    ]

    parts.append(f'''
    <defs>
      <linearGradient id="bodyGrad" x1="0%" y1="0%" x2="100%" y2="100%">
        <stop offset="0%"   stop-color="{start_color}"/>
        <stop offset="100%" stop-color="{end_color}"/>
      </linearGradient>
      <radialGradient id="aperture" cx="50%" cy="50%" r="60%">
        <stop offset="0%"  stop-color="#fff3d6" stop-opacity="0.95"/>
        <stop offset="60%" stop-color="{end_color}" stop-opacity="0.5"/>
        <stop offset="100%" stop-color="{end_color}" stop-opacity="0"/>
      </radialGradient>
      <radialGradient id="jewel" cx="35%" cy="35%" r="65%">
        <stop offset="0%"   stop-color="#fff" stop-opacity="0.95"/>
        <stop offset="50%"  stop-color="{end_color}" stop-opacity="0.8"/>
        <stop offset="100%" stop-color="#1a0e22" stop-opacity="0.4"/>
      </radialGradient>
    </defs>
    ''')

    # background
    parts.append(f'<rect width="{W}" height="{H}" fill="#0d0a16"/>')
    parts.append(
        f'<circle cx="{cx}" cy="{cy}" r="{r_max + 100}" '
        f'fill="{start_color}" opacity="0.06"/>'
    )
    parts.append(
        f'<circle cx="{cx}" cy="{cy}" r="{r_max + 50}" '
        f'fill="{end_color}" opacity="0.05"/>'
    )

    # shell body
    body_path = _band_path(inner_pts, outer_pts)
    parts.append(
        f'<path d="{body_path}" fill="url(#bodyGrad)" '
        f'stroke="#2a1f3a" stroke-width="0.8"/>'
    )

    # septa (chamber ridges across the body)
    septa_step = 16 if "debug" in themes else (20 if "build" in themes else 18)
    for i in range(septa_step, len(centerline) - 5, septa_step):
        ix, iy = inner_pts[i][0], inner_pts[i][1]
        ox, oy = outer_pts[i][0], outer_pts[i][1]
        parts.append(
            f'<line x1="{ix:.2f}" y1="{iy:.2f}" '
            f'x2="{ox:.2f}" y2="{oy:.2f}" '
            f'stroke="#1a0e22" stroke-width="0.9" opacity="0.55"/>'
        )

    # longitudinal pattern bands along the spiral
    for k, (frac, op) in enumerate([(0.25, 0.35), (0.5, 0.45), (0.75, 0.35)]):
        band = []
        for (ox, oy, *_), (ix, iy, *_) in zip(outer_pts, inner_pts):
            bx = ix + (ox - ix) * frac
            by = iy + (oy - iy) * frac
            band.append((bx, by))
        path_d = "M " + " L ".join(f"{x:.2f} {y:.2f}" for x, y in band)
        color = end_color if frac > 0.5 else start_color
        parts.append(
            f'<path d="{path_d}" fill="none" stroke="{color}" '
            f'stroke-width="0.8" opacity="{op}"/>'
        )

    # centerline cream highlight
    parts.append(
        f'<path d="{_stroke_path(centerline)}" fill="none" '
        f'stroke="#f5e8c8" stroke-width="0.6" opacity="0.55"/>'
    )

    # dead-end knots ON the body
    for de in dead_ends:
        pos = max(0.03, min(0.97, float(de.get("position", 0.5))))
        idx = int(pos * (len(centerline) - 1))
        x, y, _, r, _ = centerline[idx]
        th = thickness_at(idx, len(centerline))
        parts.append(
            f'<circle cx="{x:.2f}" cy="{y:.2f}" r="{max(3.5, th*0.35):.2f}" '
            f'fill="#0e0719" stroke="{start_color}" stroke-width="1.2" '
            f'opacity="0.95"/>'
        )
        parts.append(
            f'<circle cx="{x-1:.2f}" cy="{y-1:.2f}" r="1.1" '
            f'fill="{start_color}" opacity="0.7"/>'
        )

    # gotcha jewels along the outer rim
    n_jewels = min(len(gotchas), 14)
    for i in range(n_jewels):
        frac = 0.30 + (i / max(1, n_jewels)) * 0.65
        idx = int(frac * (len(outer_pts) - 1))
        ox, oy, _, _, n = outer_pts[idx]
        jx = ox + math.cos(n) * 3.5
        jy = oy + math.sin(n) * 3.5
        parts.append(
            f'<circle cx="{jx:.2f}" cy="{jy:.2f}" r="4.5" '
            f'fill="url(#jewel)" opacity="0.95" '
            f'stroke="#fff7e0" stroke-width="0.4" stroke-opacity="0.5"/>'
        )

    # aperture (breakthrough mouth) at the spiral's end
    bidx = len(centerline) - 1
    bx, by, _, br, bn = centerline[bidx]
    bth = thickness_at(bidx, len(centerline))
    parts.append(
        f'<ellipse cx="{bx:.2f}" cy="{by:.2f}" '
        f'rx="{bth*1.25:.2f}" ry="{bth*0.95:.2f}" '
        f'transform="rotate({math.degrees(bn):.1f} {bx:.2f} {by:.2f})" '
        f'fill="url(#aperture)" opacity="0.95"/>'
    )
    parts.append(
        f'<ellipse cx="{bx:.2f}" cy="{by:.2f}" '
        f'rx="{bth*0.45:.2f}" ry="{bth*0.30:.2f}" '
        f'transform="rotate({math.degrees(bn):.1f} {bx:.2f} {by:.2f})" '
        f'fill="#fff7e0" opacity="0.85"/>'
    )

    # signature
    parts.append(
        f'<text x="{W-14}" y="{H-14}" text-anchor="end" '
        f'fill="#7a6f96" font-size="10" opacity="0.65" font-style="italic">'
        f'turboskillslug · {duration}m · {len(approaches)} tried · '
        f'{len(dead_ends)} stumbles · {len(gotchas)} jewels</text>'
    )

    parts.append("</svg>")
    return "\n".join(parts)


if __name__ == "__main__":
    from pathlib import Path
    samples = {
        "frustrated_debug": {
            "duration_minutes": 47,
            "themes": ["debug", "build"],
            "approaches_tried": [
                {"approach": "naive regex", "outcome": "too brittle"},
                {"approach": "ast parser", "outcome": "got there"},
            ],
            "dead_ends": [
                {"position": 0.15, "what_happened": "regex backtracked"},
                {"position": 0.42, "what_happened": "missing edge case"},
                {"position": 0.61, "what_happened": "wrong import"},
            ],
            "breakthroughs": [{"position": 0.88, "what_worked": "ast walk"}],
            "gotchas": ["null nodes", "tabs vs spaces", "comments",
                        "windows line endings", "unicode in identifiers"],
            "sentiment_arc": {"start": "frustrated", "end": "resolved"},
        },
        "curious_explore": {
            "duration_minutes": 22,
            "themes": ["explore"],
            "approaches_tried": [{"approach": "skim docs", "outcome": "got it"}],
            "dead_ends": [],
            "breakthroughs": [{"position": 0.92, "what_worked": "aha"}],
            "gotchas": ["api changed in v3"],
            "sentiment_arc": {"start": "curious", "end": "enlightened"},
        },
        "long_grind": {
            "duration_minutes": 120,
            "themes": ["build", "debug"],
            "approaches_tried": [{"approach": f"a{i}", "outcome": "fail"} for i in range(5)],
            "dead_ends": [{"position": p / 10, "what_happened": "x"}
                          for p in [1, 2, 3, 4, 5, 6, 7, 8]],
            "breakthroughs": [{"position": 0.95, "what_worked": "y"}],
            "gotchas": [f"g{i}" for i in range(10)],
            "sentiment_arc": {"start": "focused", "end": "exhausted"},
        },
    }
    for name, sample in samples.items():
        Path(f"sample_{name}.svg").write_text(generate_shell_svg(sample))
        print(f"wrote sample_{name}.svg")
