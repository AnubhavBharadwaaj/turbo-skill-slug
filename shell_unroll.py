"""
Path-following scroll unroll: the spiral lays down ALONG its arm, led by a 3D curl.

The shell's `growth` parameter truncates the spiral along its own arm (not
radially), so a sequence of growth stages IS a scroll unrolling along the spiral
path: an outer ring stays hidden until the arm reaches it, even if an inner point
at the same clock-angle is already laid down.

We render N growth stages as a flipbook stacked in one SVG. Each stage is shown
in sequence via SMIL (set/animate on opacity), so the laid parchment grows along
the arm. A 3D curl object (a small cylinder with a gold highlight and a cast
shadow) rides the leading tip via animateMotion along the centerline path,
shrinking as it spends its paper, then vanishes at the rim.

This is heavier than a single-SVG animation (~1.6MB for 14 stages) but it is the
only way to get a genuine path-following reveal of a filled spiral.
"""

from __future__ import annotations

import math
import re

N_STAGES = 14
UNROLL_DUR = 3.6          # total seconds
EYE_X, EYE_Y = 320.0, 335.0


def _centerline_d(svg: str) -> str | None:
    m = re.search(r'<path class="shell-centerline" d="([^"]*)"', svg)
    return m.group(1) if m else None


def _curl_object(stage_frac: float) -> str:
    """A 3D paper-curl cylinder, sized for how much paper remains (shrinks as the
    scroll unrolls). Returned as a <g id="curl"> to be motion-animated."""
    # remaining paper ~ (1 - stage_frac); curl radius shrinks from ~16 to ~5
    r = 5 + 11 * (1 - stage_frac)
    return (
        f'<g id="paper-curl">'
        # cast shadow on the parchment just behind the curl
        f'<ellipse cx="2" cy="{r*0.6:.1f}" rx="{r*1.1:.1f}" ry="{r*0.45:.1f}" '
        f'fill="#1a1410" opacity="0.28"/>'
        # the cylinder body (the rolled paper, seen end-on)
        f'<ellipse cx="0" cy="0" rx="{r:.1f}" ry="{r*0.78:.1f}" '
        f'fill="#d8c79a" stroke="#8a7340" stroke-width="1"/>'
        # inner roll rings (paper thickness)
        f'<ellipse cx="0" cy="0" rx="{r*0.6:.1f}" ry="{r*0.46:.1f}" '
        f'fill="none" stroke="#a8915c" stroke-width="0.8" opacity="0.7"/>'
        f'<ellipse cx="0" cy="0" rx="{r*0.28:.1f}" ry="{r*0.22:.1f}" '
        f'fill="#bda874" stroke="#8a7340" stroke-width="0.6"/>'
        # gold highlight on the rounded leading edge
        f'<ellipse cx="{-r*0.4:.1f}" cy="{-r*0.3:.1f}" rx="{r*0.34:.1f}" '
        f'ry="{r*0.2:.1f}" fill="#efe0b0" opacity="0.85"/>'
        f'</g>'
    )


def build_unroll_doc(stage_svgs: list[str]) -> str:
    """Stack growth-stage SVGs as a flipbook + a curl riding the tip. Returns one
    SVG string with SMIL timing. stage_svgs[i] is the shell at growth (i+1)/N.

    Each stage is wrapped in a <g> that becomes visible at its time slot and
    hides when the next appears, so the laid parchment advances along the arm.
    The final stage stays visible (freeze).
    """
    n = len(stage_svgs)
    slot = UNROLL_DUR / n

    # strip the outer <svg ...> wrapper from each stage, keep inner content
    def inner(s):
        a = s.find(">", s.find("<svg")) + 1
        b = s.rfind("</svg>")
        return s[a:b]

    # the background (sky, particles) is identical across stages; take it from
    # the LAST stage once, render it always-on underneath, and only flip the
    # SHELL portion. But simplest robust approach: each stage is a full frame;
    # show one at a time. The sky is identical so no flicker on the backdrop.
    layers = []
    for i, s in enumerate(stage_svgs):
        begin = i * slot
        content = inner(s)
        if i < n - 1:
            # visible during its slot only
            anim = (
                f'<set attributeName="opacity" to="1" begin="{begin:.2f}s"/>'
                f'<set attributeName="opacity" to="0" begin="{begin+slot:.2f}s"/>'
            )
            start_op = "1" if i == 0 else "0"
        else:
            # final stage: appears and freezes
            anim = f'<set attributeName="opacity" to="1" begin="{begin:.2f}s"/>'
            start_op = "0"
        layers.append(
            f'<g opacity="{start_op}">{anim}{content}</g>'
        )

    # the 3D curl rides the centerline path of the FINAL stage (full spiral),
    # via animateMotion, shrinking over the unroll, vanishing at the end.
    cl = _centerline_d(stage_svgs[-1])
    curl_layer = ""
    if cl:
        curl = _curl_object(0.0)
        curl_layer = (
            f'<g>{curl}'
            f'<animateMotion dur="{UNROLL_DUR}s" begin="0s" fill="freeze" '
            f'rotate="auto" keyPoints="0;1" keyTimes="0;1" calcMode="linear" '
            f'path="{cl}"/>'
            # shrink the curl as it spends paper
            f'<animateTransform attributeName="transform" type="scale" '
            f'additive="sum" from="1.6" to="0.5" dur="{UNROLL_DUR}s" begin="0s" '
            f'fill="freeze"/>'
            # vanish at the very end
            f'<animate attributeName="opacity" values="1;1;0" keyTimes="0;0.92;1" '
            f'dur="{UNROLL_DUR}s" begin="0s" fill="freeze"/>'
            f'</g>'
        )

    W = H = 640
    body = "".join(layers) + curl_layer
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" '
        f'width="{W}" height="{H}">{body}</svg>'
    )
