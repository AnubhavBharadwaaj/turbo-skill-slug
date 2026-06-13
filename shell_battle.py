"""
Byobu battle layer for the shell.

The nautilus IS the battlefield. The spiral is the campaign path: the eye is
where the session began, the outward sweep is time. Session events become
stylized ink-on-gold figures, in the flat perspective of Japanese folding
screens (byobu):

  developer    -> the lone general near the eye, a banner at their side
  dead ends    -> fallen warriors + broken banners at their spiral positions
  gotchas      -> archers along the outer rim (the ambushes)
  breakthrough -> the dragon coiled at the aperture, a victory banner upright
  sentiment    -> gold cloud-bands and a few hill/pine terrain strokes

Figures are dark ink silhouettes riding on gold-leaf cloud bands. They are
drawn small so they sit IN the landscape, not over it.

The layer is produced from the SAME spiral geometry the shell uses, so a
fallen warrior sits exactly where its dead-end knot is.
"""

from __future__ import annotations

import math
import random


# Ink + gold palette (byobu). The figures are near-black sumi ink; the clouds
# and banners are gold leaf. These are fixed, not sentiment-driven, because the
# byobu convention is ink-on-gold regardless of the campaign's mood (the mood
# lives in the shell's own colors underneath).
INK = "#1a1410"
INK_SOFT = "#2c2218"
GOLD = "#c8a24c"
GOLD_BRIGHT = "#e6c870"
GOLD_PALE = "#efe0b0"



def _gold_backing(x: float, y: float, r: float) -> str:
    """A gold-leaf disc behind a figure so dark ink reads against gold. A faint
    dark ring keeps the figure legible even on gold-heavy (warm) shells where
    the gold backing would otherwise blend into the body."""
    return (
        f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r + 1.5:.1f}" fill="{INK}" opacity="0.30"/>'
        f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r:.1f}" fill="{GOLD}" opacity="0.62"/>'
        f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r:.1f}" fill="none" '
        f'stroke="{INK}" stroke-width="0.8" opacity="0.45"/>'
    )

def _cloud_band(cx: float, cy: float, w: float, h: float, seed: int) -> str:
    """A gold-leaf byobu cloud band: a soft lobed cloud (smooth quad curves).

    Real byobu clouds are scalloped, billowing shapes, not rectangles. We build
    a closed path of rounded lobes along the top and bottom edges.
    """
    rng = random.Random(seed)
    n = rng.randint(4, 6)
    left = cx - w / 2
    step = w / n
    # top edge: a series of upward lobes; bottom edge: downward lobes
    d = f"M {left:.1f} {cy:.1f} "
    x = left
    for i in range(n):
        nx = x + step
        peak = cy - h / 2 - rng.uniform(0, h * 0.3)
        d += f"Q {x + step/2:.1f} {peak:.1f} {nx:.1f} {cy:.1f} "
        x = nx
    for i in range(n):
        nx = x - step
        trough = cy + h / 2 + rng.uniform(0, h * 0.3)
        d += f"Q {x - step/2:.1f} {trough:.1f} {nx:.1f} {cy:.1f} "
        x = nx
    d += "Z"
    return (
        f'<path d="{d}" fill="{GOLD}" opacity="0.20"/>'
        f'<path d="{d}" fill="none" stroke="{GOLD_BRIGHT}" '
        f'stroke-width="0.7" opacity="0.4"/>'
    )


def _banner(x: float, y: float, h: float, color: str, broken: bool = False,
            angle: float = 0.0) -> str:
    """A small byobu banner on a pole. Broken = leaning, torn."""
    pole_top = (x, y - h)
    lean = 28 if broken else 0
    tx = x + math.sin(math.radians(angle + lean)) * h
    ty = y - math.cos(math.radians(angle + lean)) * h
    pole = (
        f'<line x1="{x:.1f}" y1="{y:.1f}" x2="{tx:.1f}" y2="{ty:.1f}" '
        f'stroke="{INK}" stroke-width="1.1" stroke-linecap="round"/>'
    )
    # flag near the top of the pole
    fx, fy = tx, ty
    fw = h * 0.5
    fh = h * 0.42
    if broken:
        # torn flag: a notched quad
        flag = (
            f'<path d="M {fx:.1f} {fy:.1f} L {fx+fw:.1f} {fy+fh*0.2:.1f} '
            f'L {fx+fw*0.7:.1f} {fy+fh*0.5:.1f} L {fx+fw:.1f} {fy+fh*0.8:.1f} '
            f'L {fx:.1f} {fy+fh:.1f} Z" fill="{color}" opacity="0.85"/>'
        )
    else:
        flag = (
            f'<path d="M {fx:.1f} {fy:.1f} L {fx+fw:.1f} {fy+fh*0.25:.1f} '
            f'L {fx+fw:.1f} {fy+fh*0.75:.1f} L {fx:.1f} {fy+fh:.1f} Z" '
            f'fill="{color}" opacity="0.9"/>'
        )
    return pole + flag


def _kabuto(x: float, y: float, s: float, ink: str) -> str:
    """A kabuto helmet silhouette with the crescent (maedate) crest."""
    # dome
    dome = (
        f'<path d="M {x - s*0.26:.1f} {y:.1f} '
        f'Q {x:.1f} {y - s*0.42:.1f} {x + s*0.26:.1f} {y:.1f} Z" fill="{ink}"/>'
    )
    # neck guard (shikoro) flare
    flare = (
        f'<path d="M {x - s*0.30:.1f} {y:.1f} L {x - s*0.34:.1f} {y + s*0.12:.1f} '
        f'L {x + s*0.34:.1f} {y + s*0.12:.1f} L {x + s*0.30:.1f} {y:.1f} Z" '
        f'fill="{ink}"/>'
    )
    # crescent crest (maedate) - two horns
    crest = (
        f'<path d="M {x - s*0.22:.1f} {y - s*0.12:.1f} '
        f'Q {x:.1f} {y - s*0.55:.1f} {x + s*0.22:.1f} {y - s*0.12:.1f} '
        f'Q {x:.1f} {y - s*0.34:.1f} {x - s*0.22:.1f} {y - s*0.12:.1f} Z" '
        f'fill="{ink}"/>'
    )
    return dome + flare + crest


def _katana(x1, y1, x2, y2, ink) -> str:
    """A katana: a slightly curved blade stroke with a guard."""
    mx = (x1 + x2) / 2 + (y2 - y1) * 0.12
    my = (y1 + y2) / 2 - (x2 - x1) * 0.12
    blade = (
        f'<path d="M {x1:.1f} {y1:.1f} Q {mx:.1f} {my:.1f} {x2:.1f} {y2:.1f}" '
        f'fill="none" stroke="{ink}" stroke-width="1.4" stroke-linecap="round"/>'
    )
    guard = f'<circle cx="{x1:.1f}" cy="{y1:.1f}" r="1.6" fill="{ink}"/>'
    return blade + guard


def _general(x: float, y: float, s: float) -> str:
    """The developer: a standing samurai general, kabuto + katana raised."""
    # torso (armored, slightly trapezoidal do)
    torso = (
        f'<path d="M {x - s*0.20:.1f} {y - s*0.52:.1f} '
        f'L {x - s*0.30:.1f} {y:.1f} L {x + s*0.30:.1f} {y:.1f} '
        f'L {x + s*0.20:.1f} {y - s*0.52:.1f} Z" fill="{INK}"/>'
    )
    # armor lames (two horizontal segment lines)
    lames = (
        f'<line x1="{x - s*0.26:.1f}" y1="{y - s*0.16:.1f}" '
        f'x2="{x + s*0.26:.1f}" y2="{y - s*0.16:.1f}" stroke="{GOLD_PALE}" '
        f'stroke-width="0.6" opacity="0.5"/>'
        f'<line x1="{x - s*0.22:.1f}" y1="{y - s*0.04:.1f}" '
        f'x2="{x + s*0.22:.1f}" y2="{y - s*0.04:.1f}" stroke="{GOLD_PALE}" '
        f'stroke-width="0.6" opacity="0.5"/>'
    )
    # head + kabuto
    head = f'<circle cx="{x:.1f}" cy="{y - s*0.60:.1f}" r="{s*0.12:.1f}" fill="{INK}"/>'
    helm = _kabuto(x, y - s*0.64, s*0.9, INK)
    # katana raised diagonally
    sword = _katana(x + s*0.24, y - s*0.30, x + s*0.62, y - s*0.78, INK)
    return torso + lames + head + helm + sword


def _fallen(x: float, y: float, s: float, ink: str) -> str:
    """A fallen warrior: toppled samurai, kabuto askew, katana dropped."""
    # body lying down (rotated trapezoid torso)
    g = f'<g transform="rotate(82 {x:.1f} {y:.1f})" opacity="0.9">'
    torso = (
        f'<path d="M {x - s*0.18:.1f} {y - s*0.48:.1f} '
        f'L {x - s*0.26:.1f} {y:.1f} L {x + s*0.26:.1f} {y:.1f} '
        f'L {x + s*0.18:.1f} {y - s*0.48:.1f} Z" fill="{ink}"/>'
    )
    head = f'<circle cx="{x:.1f}" cy="{y - s*0.56:.1f}" r="{s*0.11:.1f}" fill="{ink}"/>'
    helm = _kabuto(x, y - s*0.60, s*0.8, ink)
    g_end = '</g>'
    # dropped katana lying separately, near the body
    sword = _katana(x - s*0.5, y + s*0.15, x - s*0.05, y + s*0.30, ink)
    return g + torso + head + helm + g_end + sword


def _archer(x: float, y: float, s: float, ink: str) -> str:
    """A samurai archer: kneeling, drawing a tall asymmetric yumi bow."""
    # kneeling body
    body = (
        f'<path d="M {x - s*0.05:.1f} {y - s*0.40:.1f} '
        f'L {x - s*0.28:.1f} {y:.1f} L {x + s*0.10:.1f} {y:.1f} Z" fill="{ink}"/>'
    )
    head = f'<circle cx="{x - s*0.02:.1f}" cy="{y - s*0.48:.1f}" r="{s*0.10:.1f}" fill="{ink}"/>'
    helm = _kabuto(x - s*0.02, y - s*0.52, s*0.7, ink)
    # tall yumi bow (asymmetric: grip below center, long upper limb)
    bx = x + s * 0.28
    bow = (
        f'<path d="M {bx:.1f} {y - s*0.75:.1f} '
        f'Q {bx + s*0.34:.1f} {y - s*0.15:.1f} {bx:.1f} {y + s*0.32:.1f}" '
        f'fill="none" stroke="{ink}" stroke-width="1.1"/>'
    )
    # bowstring + nocked arrow drawn back
    string = (
        f'<line x1="{bx:.1f}" y1="{y - s*0.75:.1f}" x2="{bx:.1f}" y2="{y + s*0.32:.1f}" '
        f'stroke="{ink}" stroke-width="0.5"/>'
    )
    arrow = (
        f'<line x1="{x + s*0.02:.1f}" y1="{y - s*0.30:.1f}" '
        f'x2="{bx + s*0.10:.1f}" y2="{y - s*0.30:.1f}" stroke="{ink}" stroke-width="0.7"/>'
    )
    return body + head + helm + bow + string + arrow


def _dragon(x: float, y: float, s: float, angle_deg: float) -> str:
    """The breakthrough: an Eastern dragon, maned head + horns + sinuous segmented
    body + clawed legs, coiling toward the aperture."""
    seg = s
    a = math.radians(angle_deg)
    # build the spine path
    d = f"M {x:.1f} {y:.1f} "
    px, py = x, y
    spine = [(px, py)]
    for i in range(1, 8):
        swing = (1 if i % 2 else -1) * seg * 0.55
        nx = px + math.cos(a) * seg * 0.55 + math.cos(a + math.pi/2) * swing
        ny = py + math.sin(a) * seg * 0.55 + math.sin(a + math.pi/2) * swing
        d += f"Q {px + math.cos(a+math.pi/2)*swing:.1f} {py + math.sin(a+math.pi/2)*swing:.1f} {nx:.1f} {ny:.1f} "
        spine.append((nx, ny))
        px, py = nx, ny
    body = (
        f'<path d="{d}" fill="none" stroke="{INK}" stroke-width="{s*0.30:.1f}" '
        f'stroke-linecap="round" opacity="0.92"/>'
    )
    # dorsal ridge: small spikes along the spine
    spikes = ""
    for i in range(1, len(spine) - 1, 2):
        sx, sy = spine[i]
        spikes += (
            f'<circle cx="{sx:.1f}" cy="{sy:.1f}" r="{s*0.07:.1f}" fill="{INK}"/>'
        )
    # clawed legs at two points
    legs = ""
    for i in (2, 5):
        if i < len(spine):
            lx, ly = spine[i]
            legs += (
                f'<line x1="{lx:.1f}" y1="{ly:.1f}" x2="{lx - s*0.3:.1f}" '
                f'y2="{ly + s*0.3:.1f}" stroke="{INK}" stroke-width="{s*0.10:.1f}" '
                f'stroke-linecap="round"/>'
            )
    # head at the start (where the dragon faces): maned, horned, gold eye
    hx, hy = x, y
    head = (
        f'<circle cx="{hx:.1f}" cy="{hy:.1f}" r="{s*0.26:.1f}" fill="{INK}"/>'
        # two horns
        f'<line x1="{hx - s*0.1:.1f}" y1="{hy - s*0.18:.1f}" '
        f'x2="{hx - s*0.28:.1f}" y2="{hy - s*0.42:.1f}" stroke="{INK}" '
        f'stroke-width="{s*0.06:.1f}" stroke-linecap="round"/>'
        f'<line x1="{hx + s*0.1:.1f}" y1="{hy - s*0.18:.1f}" '
        f'x2="{hx + s*0.18:.1f}" y2="{hy - s*0.44:.1f}" stroke="{INK}" '
        f'stroke-width="{s*0.06:.1f}" stroke-linecap="round"/>'
        # mane (a few short strokes behind the head)
        f'<path d="M {hx + s*0.2:.1f} {hy:.1f} q {s*0.2:.1f} {s*0.1:.1f} {s*0.12:.1f} {s*0.3:.1f}" '
        f'fill="none" stroke="{INK}" stroke-width="{s*0.05:.1f}"/>'
        # gold eye
        f'<circle cx="{hx + s*0.08:.1f}" cy="{hy - s*0.06:.1f}" r="{s*0.06:.1f}" '
        f'fill="{GOLD_BRIGHT}"/>'
    )
    return body + spikes + legs + head


def _point_at_radius_frac(centerline, rfrac):
    """Find the spiral point whose radius is closest to rfrac of the max radius.

    The log-spiral bunches points near the eye, so placing by point-index
    clusters figures in the center. Placing by RADIUS spreads them across the
    visible outer arms where there is room for figures.
    """
    if not centerline:
        return None
    radii = [p[3] for p in centerline]  # r is index 3
    r_min, r_max = min(radii), max(radii)
    target = r_min + (r_max - r_min) * rfrac
    best_i = min(range(len(centerline)), key=lambda i: abs(radii[i] - target))
    return centerline[best_i]


def build_battle_layer(features: dict, centerline: list, outer_pts: list,
                       thickness_at, n_full: int, pal: dict, seed: int) -> str:
    """Return the byobu battle layer SVG, placed on the shell's spiral by RADIUS
    so figures spread across the visible outer arms (not the bunched eye).

    Each figure sits on a gold backing (byobu ink-on-gold). Figures are sized to
    be legible on the 640px canvas.
    """
    rng = random.Random(seed ^ 0xBA771E)
    dead_ends = features.get("dead_ends", []) or []
    gotchas = features.get("gotchas", []) or []

    parts = ["<g class=\"battle-layer\">"]

    # ---- gold cloud bands drifting across the OUTER field ----
    for i in range(3):
        rfrac = 0.55 + 0.15 * i
        p = _point_at_radius_frac(centerline, min(0.95, rfrac))
        if p:
            x, y = p[0], p[1]
            parts.append(_cloud_band(x, y, w=rng.uniform(120, 180),
                                     h=rng.uniform(30, 44), seed=seed + i))

    # ---- the general (developer): pushed to a clear mid-outer arm so it does
    # not pile onto the figures near the crowded eye ----
    p = _point_at_radius_frac(centerline, 0.66)
    if p:
        gx, gy = p[0], p[1]
        parts.append(_gold_backing(gx, gy - 10, 30))
        parts.append(_general(gx, gy, s=40))
        parts.append(_banner(gx + 26, gy + 4, h=46, color=INK))

    # ---- fallen warriors at each dead end, placed by RADIUS ----
    # Map each dead-end's position (0..1) to a radius fraction in the OUTER
    # two-thirds of the shell so they land on visible arms.
    for de in dead_ends:
        pos = max(0.0, min(1.0, float(de.get("position", 0.5))))
        rfrac = 0.48 + pos * 0.46  # 0.48 .. 0.94 (keep out of the crowded eye)
        p = _point_at_radius_frac(centerline, rfrac)
        if not p:
            continue
        x, y = p[0], p[1]
        parts.append(_gold_backing(x, y, 22))
        parts.append(_fallen(x, y, s=28, ink=INK))
        parts.append(_banner(x + 12, y - 2, h=26, color=INK, broken=True,
                             angle=rng.uniform(-12, 12)))

    # ---- archers along the rim at each gotcha (outer rim, by index is fine
    # here because outer_pts already traces the visible outer edge) ----
    n_arch = min(len(gotchas), 8)
    for i in range(n_arch):
        frac = 0.52 + (i / max(1, n_arch)) * 0.44
        idx = int(frac * (len(outer_pts) - 1)) if outer_pts else 0
        if idx >= len(outer_pts):
            continue
        ox, oy, _, _, nrm = outer_pts[idx]
        ax = ox + math.cos(nrm) * 18
        ay = oy + math.sin(nrm) * 18
        parts.append(_gold_backing(ax, ay, 15))
        parts.append(_archer(ax, ay, s=24, ink=INK))

    # ---- the dragon (breakthrough): placed just BEFORE the aperture tip so it
    # is not washed out by the aperture glow, larger, coiling toward the mouth ----
    tip = centerline[-1]
    pre = centerline[max(0, len(centerline) - 18)]  # a little back from the tip
    dx, dy = pre[0], pre[1]
    bn = tip[4]
    # a darker gold cloud behind the dragon so it reads against the glow
    parts.append(
        f'<ellipse cx="{dx:.1f}" cy="{dy:.1f}" rx="46" ry="30" '
        f'transform="rotate({math.degrees(bn):.0f} {dx:.1f} {dy:.1f})" '
        f'fill="{GOLD}" opacity="0.30"/>'
    )
    parts.append(_dragon(dx, dy, s=42, angle_deg=math.degrees(bn) + 150))
    parts.append(_banner(dx - 20, dy + 10, h=56, color=INK))

    parts.append("</g>")
    return "\n".join(parts)
