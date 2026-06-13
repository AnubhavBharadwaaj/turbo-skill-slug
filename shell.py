"""
Shell generator for TurboSkillSlug.

Every shell is unique because every session is unique. The patterns are
derived from the session, not decorative: duration shapes the spiral,
dead ends leave dark knots, breakthroughs open the aperture, gotchas
become iridescent jewels, and the sentiment arc drives the color story.

Visual techniques:
  - SVG feTurbulence for mother-of-pearl (nacre) texture
  - feGaussianBlur composites for glow on aperture and jewels
  - Multi-stop radial gradients for depth
  - HSL-derived color harmonies from sentiment
  - Cubic bezier smoothing on the spiral body
  - Layered transparency for organic depth

Staged growth:
  generate_shell_svg(features, growth=g) renders the shell at completion
  fraction g in [0,1]. At g<1 the spiral is physically shorter, only the
  knots and jewels up to that point have formed, and the aperture (the
  breakthrough mouth) stays closed until g reaches 1.0 - the breakthrough
  is the last thing to open. growth=1.0 is byte-identical in intent to the
  original single-shot render.
"""

import colorsys
import math
import random
from typing import Any


# ---------------------------------------------------------------------------
# HSL-based color system derived from sentiment
# ---------------------------------------------------------------------------

SENTIMENT_HUES: dict[str, float] = {
    "confused": 0.75,     # violet
    "focused": 0.61,      # deep blue
    "frustrated": 0.0,    # red
    "curious": 0.50,      # teal
    "resolved": 0.39,     # green
    "joyful": 0.12,       # warm gold
    "exhausted": 0.67,    # grey-blue
    "enlightened": 0.14,  # pale gold
}


def _hue_for(sentiment: str, fallback: float = 0.75) -> float:
    return SENTIMENT_HUES.get(sentiment.lower().strip(), fallback)


def _hsl_to_hex(h: float, s: float, l: float) -> str:
    r, g, b = colorsys.hls_to_rgb(h, l, s)
    return f"#{int(r*255):02x}{int(g*255):02x}{int(b*255):02x}"


def _palette(start_sent: str, end_sent: str) -> dict[str, str]:
    """Derive a harmonious 6-color palette from start/end sentiment."""
    h0 = _hue_for(start_sent, 0.75)
    h1 = _hue_for(end_sent, 0.39)
    return {
        "bg_deep":       _hsl_to_hex(h0, 0.30, 0.06),
        "bg_mid":        _hsl_to_hex(h0, 0.25, 0.12),
        "body_dark":     _hsl_to_hex(h0, 0.35, 0.30),
        "body_light":    _hsl_to_hex(h1, 0.40, 0.50),
        "accent":        _hsl_to_hex(h1, 0.55, 0.65),
        "highlight":     _hsl_to_hex(h1, 0.30, 0.85),
        "aperture_core": _hsl_to_hex(h1, 0.20, 0.92),
        "jewel":         _hsl_to_hex((h0 + h1) / 2, 0.60, 0.70),
        "knot":          _hsl_to_hex(h0, 0.40, 0.10),
        "septa":         _hsl_to_hex(h0, 0.20, 0.15),
    }


# ---------------------------------------------------------------------------
# Spiral geometry
# ---------------------------------------------------------------------------

def _log_spiral(cx: float, cy: float, n_turns: float,
                r0: float, r_max: float, n_points: int = 500):
    """Generate points along a logarithmic spiral with normals."""
    t_max = 2 * math.pi * max(n_turns, 0.5)
    b = math.log(max(r_max, r0 + 1) / r0) / t_max
    pts = []
    for i in range(n_points):
        t = (i / (n_points - 1)) * t_max
        r = r0 * math.exp(b * t)
        x = cx + r * math.cos(t)
        y = cy + r * math.sin(t)
        tangent = t + math.atan2(1, b)
        normal = tangent + math.pi / 2
        pts.append((x, y, t, r, normal))
    return pts


def _smooth_path(pts: list, closed: bool = False) -> str:
    """Convert points to a smooth SVG path using cubic bezier approximation."""
    if len(pts) < 2:
        return ""
    d = [f"M {pts[0][0]:.1f} {pts[0][1]:.1f}"]
    tension = 0.3
    for i in range(1, len(pts)):
        p0 = pts[max(i - 2, 0)]
        p1 = pts[i - 1]
        p2 = pts[i]
        p3 = pts[min(i + 1, len(pts) - 1)]
        cp1x = p1[0] + (p2[0] - p0[0]) * tension
        cp1y = p1[1] + (p2[1] - p0[1]) * tension
        cp2x = p2[0] - (p3[0] - p1[0]) * tension
        cp2y = p2[1] - (p3[1] - p1[1]) * tension
        d.append(f"C {cp1x:.1f} {cp1y:.1f} {cp2x:.1f} {cp2y:.1f} {p2[0]:.1f} {p2[1]:.1f}")
    if closed:
        d.append("Z")
    return " ".join(d)


def _band_path_smooth(inner: list, outer: list) -> str:
    """Closed smooth path for the shell body (outer forward, inner reverse)."""
    fwd = _smooth_path(outer)
    rev_pts = list(reversed(inner))
    if rev_pts:
        rev = f"L {rev_pts[0][0]:.1f} {rev_pts[0][1]:.1f} "
        tension = 0.3
        for i in range(1, len(rev_pts)):
            p0 = rev_pts[max(i - 2, 0)]
            p1 = rev_pts[i - 1]
            p2 = rev_pts[i]
            p3 = rev_pts[min(i + 1, len(rev_pts) - 1)]
            cp1x = p1[0] + (p2[0] - p0[0]) * tension
            cp1y = p1[1] + (p2[1] - p0[1]) * tension
            cp2x = p2[0] - (p3[0] - p1[0]) * tension
            cp2y = p2[1] - (p3[1] - p1[1]) * tension
            rev += f"C {cp1x:.1f} {cp1y:.1f} {cp2x:.1f} {cp2y:.1f} {p2[0]:.1f} {p2[1]:.1f} "
        return fwd + " " + rev + "Z"
    return fwd + " Z"


# ---------------------------------------------------------------------------
# Main generator
# ---------------------------------------------------------------------------

def generate_shell_svg(features: dict[str, Any], growth: float = 1.0) -> str:
    """Generate a beautiful SVG shell from session features.

    growth in [0,1] controls how far the shell has formed. At growth<1 the
    spiral is truncated, only knots/jewels up to that fraction appear, and the
    aperture stays closed until growth==1.0. growth>=1.0 is the full shell.
    """
    growth = max(0.0, min(1.0, float(growth)))

    duration = max(5, min(180, int(features.get("duration_minutes", 30) or 30)))
    approaches = features.get("approaches_tried", []) or []
    dead_ends = features.get("dead_ends", []) or []
    breakthroughs = features.get("breakthroughs", []) or []
    gotchas = features.get("gotchas", []) or []
    themes = features.get("themes", []) or []
    sentiment = features.get("sentiment_arc", {}) or {}

    start_sent = sentiment.get("start", "confused")
    end_sent = sentiment.get("end", "resolved")
    pal = _palette(start_sent, end_sent)

    seed = hash(str(features.get("duration_minutes", 0))) % 10000
    rng = random.Random(seed)

    W = H = 640
    cx, cy = W / 2, H / 2 + 15

    n_turns = 2.4 + 0.35 * len(approaches) + duration / 150.0
    n_turns = min(n_turns, 4.5)
    r0 = 5
    r_max = min(W * 0.38, 65 + duration * 2.0)

    # Always compute the FULL spiral (geometry is stable); growth truncates
    # how much of it we draw, so the partial shell is a true prefix of the
    # final one (no reflow, no jitter between stages).
    full_centerline = _log_spiral(cx, cy, n_turns, r0, r_max, n_points=500)
    n_full = len(full_centerline)
    n_grown = max(2, int(round(n_full * growth)))
    centerline = full_centerline[:n_grown]

    def thickness_at(idx: int, total_full: int) -> float:
        # thickness keyed to position in the FULL spiral, so a point's
        # thickness is identical whether or not later points exist yet
        frac = idx / max(1, total_full - 1)
        return 3 + (r_max * 0.28) * (frac ** 1.35)

    outer_pts = []
    inner_pts = []
    for i, (x, y, t, r, n) in enumerate(centerline):
        th = thickness_at(i, n_full)
        outer_pts.append((x + math.cos(n) * th, y + math.sin(n) * th, t, r, n))
        inner_pts.append((x - math.cos(n) * th, y - math.sin(n) * th, t, r, n))

    svg = []
    svg.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" '
        f'width="{W}" height="{H}">'
    )

    # ---- DEFS: filters, gradients, patterns ----
    svg.append(f'''<defs>
  <!-- Nacre / mother-of-pearl: barely-there shimmer, not noise -->
  <filter id="nacre" x="-5%" y="-5%" width="110%" height="110%">
    <feTurbulence type="fractalNoise" baseFrequency="0.007 0.015"
                  numOctaves="3" seed="{seed}" result="noise"/>
    <feColorMatrix in="noise" type="saturate" values="0.2" result="colored"/>
    <feBlend in="SourceGraphic" in2="colored" mode="soft-light" result="nacred"/>
    <feComposite in="nacred" in2="SourceGraphic" operator="in"/>
  </filter>

  <!-- Glow for aperture -->
  <filter id="glow" x="-50%" y="-50%" width="200%" height="200%">
    <feGaussianBlur stdDeviation="8" result="blur"/>
    <feComposite in="SourceGraphic" in2="blur" operator="over"/>
  </filter>

  <!-- Soft glow for jewels -->
  <filter id="jewelGlow" x="-80%" y="-80%" width="260%" height="260%">
    <feGaussianBlur stdDeviation="3" result="blur"/>
    <feComposite in="SourceGraphic" in2="blur" operator="over"/>
  </filter>

  <!-- Soft shadow for depth -->
  <filter id="depth" x="-5%" y="-5%" width="110%" height="110%">
    <feGaussianBlur stdDeviation="1.5"/>
  </filter>

  <!-- Shell body gradient (high contrast, 5 stops) -->
  <radialGradient id="bodyGrad" cx="40%" cy="40%" r="70%">
    <stop offset="0%"   stop-color="{pal['highlight']}" stop-opacity="0.85"/>
    <stop offset="20%"  stop-color="{pal['body_light']}" stop-opacity="0.9"/>
    <stop offset="50%"  stop-color="{pal['accent']}" stop-opacity="0.8"/>
    <stop offset="80%"  stop-color="{pal['body_dark']}" stop-opacity="0.9"/>
    <stop offset="100%" stop-color="{pal['bg_mid']}" stop-opacity="0.95"/>
  </radialGradient>

  <!-- Aperture glow gradient -->
  <radialGradient id="apertureGrad" cx="50%" cy="50%" r="60%">
    <stop offset="0%"   stop-color="{pal['aperture_core']}" stop-opacity="0.95"/>
    <stop offset="40%"  stop-color="{pal['highlight']}" stop-opacity="0.7"/>
    <stop offset="70%"  stop-color="{pal['accent']}" stop-opacity="0.4"/>
    <stop offset="100%" stop-color="{pal['body_light']}" stop-opacity="0"/>
  </radialGradient>

  <!-- Jewel gradient -->
  <radialGradient id="jewelGrad" cx="30%" cy="30%" r="70%">
    <stop offset="0%"   stop-color="#fff" stop-opacity="0.95"/>
    <stop offset="30%"  stop-color="{pal['jewel']}" stop-opacity="0.85"/>
    <stop offset="70%"  stop-color="{pal['accent']}" stop-opacity="0.6"/>
    <stop offset="100%" stop-color="{pal['body_dark']}" stop-opacity="0.3"/>
  </radialGradient>

  <!-- Background atmosphere gradient -->
  <radialGradient id="atmosphere" cx="45%" cy="45%" r="65%">
    <stop offset="0%"   stop-color="{pal['bg_mid']}" stop-opacity="0.8"/>
    <stop offset="50%"  stop-color="{pal['bg_deep']}" stop-opacity="0.9"/>
    <stop offset="100%" stop-color="{pal['bg_deep']}" stop-opacity="1"/>
  </radialGradient>
</defs>''')

    # ---- BACKGROUND with atmosphere ----
    svg.append(f'<rect width="{W}" height="{H}" fill="{pal["bg_deep"]}"/>')
    svg.append(f'<rect width="{W}" height="{H}" fill="url(#atmosphere)"/>')

    for _ in range(40):
        px = rng.uniform(20, W - 20)
        py = rng.uniform(20, H - 20)
        pr = rng.uniform(0.3, 1.2)
        po = rng.uniform(0.15, 0.45)
        svg.append(
            f'<circle cx="{px:.1f}" cy="{py:.1f}" r="{pr:.2f}" '
            f'fill="{pal["highlight"]}" opacity="{po:.2f}"/>'
        )

    svg.append(
        f'<circle cx="{cx}" cy="{cy}" r="{r_max + 90}" '
        f'fill="{pal["body_dark"]}" opacity="0.08"/>'
    )
    svg.append(
        f'<circle cx="{cx}" cy="{cy}" r="{r_max + 50}" '
        f'fill="{pal["body_light"]}" opacity="0.06"/>'
    )

    # ---- SHELL BODY with nacre texture ----
    body_d = _band_path_smooth(inner_pts, outer_pts)
    svg.append(
        f'<path d="{body_d}" fill="{pal["bg_deep"]}" opacity="0.4" '
        f'transform="translate(3, 4)" filter="url(#depth)"/>'
    )
    svg.append(
        f'<path class="shell-body" d="{body_d}" fill="url(#bodyGrad)" '
        f'stroke="{pal["septa"]}" stroke-width="0.5" filter="url(#nacre)"/>'
    )

    # ---- SEPTA (chamber ridges) ----
    septa_step = 14 if "debug" in themes else (18 if "build" in themes else 16)
    if len(centerline) > septa_step + 8:
        total_septa = (len(centerline) - 8 - septa_step) // septa_step
        for si, i in enumerate(range(septa_step, len(centerline) - 8, septa_step)):
            ix, iy = inner_pts[i][0], inner_pts[i][1]
            ox, oy = outer_pts[i][0], outer_pts[i][1]
            frac = si / max(1, total_septa)
            opacity = 0.15 + frac * 0.35
            svg.append(
                f'<line x1="{ix:.1f}" y1="{iy:.1f}" '
                f'x2="{ox:.1f}" y2="{oy:.1f}" '
                f'stroke="{pal["septa"]}" stroke-width="0.7" '
                f'opacity="{opacity:.2f}" stroke-linecap="round"/>'
            )

    # ---- LONGITUDINAL BANDS ----
    for frac, opacity in [(0.2, 0.2), (0.4, 0.3), (0.6, 0.25), (0.8, 0.2)]:
        band = []
        for (ox, oy, *_), (ix, iy, *_) in zip(outer_pts, inner_pts):
            bx = ix + (ox - ix) * frac
            by = iy + (oy - iy) * frac
            band.append((bx, by))
        path_d = _smooth_path(band)
        color = pal["accent"] if frac > 0.5 else pal["highlight"]
        svg.append(
            f'<path d="{path_d}" fill="none" stroke="{color}" '
            f'stroke-width="0.6" opacity="{opacity}"/>'
        )

    # ---- CENTERLINE shimmer ----
    cl_path = _smooth_path(centerline)
    svg.append(
        f'<path class="shell-centerline" d="{cl_path}" fill="none" '
        f'stroke="{pal["highlight"]}" stroke-width="0.5" opacity="0.4"/>'
    )

    # ---- OUTER RIM GLOW ----
    rim_path = _smooth_path(outer_pts)
    svg.append(
        f'<path class="shell-rim" d="{rim_path}" fill="none" '
        f'stroke="{pal["accent"]}" stroke-width="2.5" opacity="0.15" '
        f'filter="url(#jewelGlow)"/>'
    )
    svg.append(
        f'<path d="{rim_path}" fill="none" '
        f'stroke="{pal["highlight"]}" stroke-width="0.8" opacity="0.5"/>'
    )

    # ---- CENTRAL EYE ----
    ex, ey = centerline[0][0], centerline[0][1]
    svg.append(
        f'<circle cx="{ex:.1f}" cy="{ey:.1f}" r="4" '
        f'fill="{pal["accent"]}" opacity="0.3" filter="url(#jewelGlow)"/>'
    )
    svg.append(
        f'<circle cx="{ex:.1f}" cy="{ey:.1f}" r="1.8" '
        f'fill="{pal["highlight"]}" opacity="0.85"/>'
    )
    svg.append(
        f'<circle cx="{ex - 0.4:.1f}" cy="{ey - 0.5:.1f}" r="0.6" '
        f'fill="#fff" opacity="0.9"/>'
    )

    # ---- DEAD-END KNOTS (only those that have formed by this growth) ----
    for de in dead_ends:
        pos = max(0.04, min(0.96, float(de.get("position", 0.5))))
        if pos > growth:
            continue  # not yet formed at this stage
        idx = int(pos * (n_full - 1))
        if idx >= len(centerline):
            continue
        x, y, _, r, _ = centerline[idx]
        th = thickness_at(idx, n_full)
        kr = max(3.5, th * 0.32)
        svg.append(
            f'<circle cx="{x + 1:.1f}" cy="{y + 1:.1f}" r="{kr + 1:.1f}" '
            f'fill="{pal["bg_deep"]}" opacity="0.5" filter="url(#depth)"/>'
        )
        svg.append(
            f'<circle class="shell-knot" cx="{x:.1f}" cy="{y:.1f}" r="{kr:.1f}" '
            f'fill="{pal["knot"]}" stroke="{pal["body_dark"]}" '
            f'stroke-width="1" opacity="0.9"/>'
        )
        svg.append(
            f'<circle cx="{x - 1:.1f}" cy="{y - 1.2:.1f}" r="{kr * 0.3:.1f}" '
            f'fill="{pal["body_dark"]}" opacity="0.6"/>'
        )

    # ---- GOTCHA JEWELS (those whose rim position has formed) ----
    n_jewels = min(len(gotchas), 12)
    for i in range(n_jewels):
        frac = 0.28 + (i / max(1, n_jewels)) * 0.65
        if frac > growth:
            continue  # rim hasn't reached this jewel yet
        idx = int(frac * (len(outer_pts) - 1)) if outer_pts else 0
        if idx >= len(outer_pts):
            continue
        ox, oy, _, _, n = outer_pts[idx]
        jx = ox + math.cos(n) * 4
        jy = oy + math.sin(n) * 4
        svg.append(
            f'<circle cx="{jx:.1f}" cy="{jy:.1f}" r="9" '
            f'fill="{pal["jewel"]}" opacity="0.3" filter="url(#jewelGlow)"/>'
        )
        svg.append(
            f'<circle class="shell-jewel" cx="{jx:.1f}" cy="{jy:.1f}" r="4.5" '
            f'fill="url(#jewelGrad)" opacity="0.95"/>'
        )
        svg.append(
            f'<circle cx="{jx - 1:.1f}" cy="{jy - 1.2:.1f}" r="1.2" '
            f'fill="#fff" opacity="0.9"/>'
        )

    # ---- APERTURE (breakthrough mouth) - opens only when fully grown ----
    # The breakthrough is the LAST thing to form. It opens as growth nears 1.0,
    # fading in over the final 15% so the reveal lands on the breakthrough.
    if growth > 0.85:
        aperture_op = min(1.0, (growth - 0.85) / 0.15)
        bidx = len(centerline) - 1
        bx, by, _, br, bn = centerline[bidx]
        bth = thickness_at(bidx, n_full)
        svg.append(
            f'<ellipse cx="{bx:.1f}" cy="{by:.1f}" '
            f'rx="{bth * 2.0:.1f}" ry="{bth * 1.5:.1f}" '
            f'transform="rotate({math.degrees(bn):.0f} {bx:.1f} {by:.1f})" '
            f'fill="{pal["accent"]}" opacity="{0.15 * aperture_op:.2f}" filter="url(#glow)"/>'
        )
        svg.append(
            f'<ellipse class="shell-aperture" cx="{bx:.1f}" cy="{by:.1f}" '
            f'rx="{bth * 1.2:.1f}" ry="{bth * 0.9:.1f}" '
            f'transform="rotate({math.degrees(bn):.0f} {bx:.1f} {by:.1f})" '
            f'fill="url(#apertureGrad)" opacity="{0.95 * aperture_op:.2f}"/>'
        )
        svg.append(
            f'<ellipse cx="{bx:.1f}" cy="{by:.1f}" '
            f'rx="{bth * 0.4:.1f}" ry="{bth * 0.28:.1f}" '
            f'transform="rotate({math.degrees(bn):.0f} {bx:.1f} {by:.1f})" '
            f'fill="{pal["aperture_core"]}" opacity="{0.9 * aperture_op:.2f}"/>'
        )

    # ---- SIGNATURE (full shell only) ----
    if growth >= 1.0:
        stats = (
            f"turboskillslug · {duration}m · {len(approaches)} tried · "
            f"{len(dead_ends)} stumbles · {len(gotchas)} jewels"
        )
        svg.append(
            f'<text x="{W - 14}" y="{H - 14}" text-anchor="end" '
            f'fill="{pal["body_light"]}" font-size="9" opacity="0.5" '
            f'font-family="Georgia, serif" font-style="italic">{stats}</text>'
        )

    svg.append("</svg>")
    return "\n".join(svg)


# ---------------------------------------------------------------------------
# Smoke test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    from pathlib import Path

    sample = {
        "duration_minutes": 47,
        "themes": ["debug", "build"],
        "approaches_tried": [
            {"approach": "naive regex", "why_it_failed": "too brittle"},
            {"approach": "ast parser", "why_it_failed": "complex setup"},
        ],
        "dead_ends": [
            {"position": 0.15, "what_happened": "regex backtracked"},
            {"position": 0.42, "what_happened": "missing edge case"},
            {"position": 0.61, "what_happened": "wrong import"},
        ],
        "breakthroughs": [{"position": 0.88, "what_worked": "ast walk"}],
        "gotchas": ["null nodes", "tabs vs spaces", "comments",
                    "windows line endings", "unicode"],
        "sentiment_arc": {"start": "frustrated", "end": "resolved"},
    }
    for g in [0.2, 0.4, 0.6, 0.8, 1.0]:
        Path(f"growth_{int(g*100)}.svg").write_text(generate_shell_svg(sample, growth=g))
        print(f"wrote growth_{int(g*100)}.svg")
