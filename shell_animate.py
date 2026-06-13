"""
Browser-rendered birth animations for the shell, using SMIL.

Gradio's gr.HTML sanitizes embedded <style> blocks, so CSS animation does not
survive. SMIL animation elements (<animate>, <animateTransform>, <set>) are part
of the SVG spec itself and render inside an <svg> even when CSS is stripped.

The shell is generated once as a static SVG. This module injects SMIL animation
into the tagged elements so the BROWSER plays a smooth one-shot birth, then
holds the final (static) frame via fill="freeze".

Three styles, chosen per shell:
  "shards" - knots & jewels fly in from scattered offsets and crystallize
  "draw"   - the spiral draws itself outward; knots/jewels bloom in sequence
  "glass"  - the shell fades up from translucent saturated glass to solid nacre

All styles end on the exact static shell (freeze), so nothing is lost.
"""

from __future__ import annotations

from anim_diagnostic import inject_probe

import random
import re

STYLES = ("shards", "draw", "glass")

# Set False for final submission; True shows a live badge reporting whether the
# SMIL animation is present and actually running inside the iframe.
DIAGNOSTIC = False


def pick_style(seed) -> str:
    return random.Random(seed).choice(STYLES)


def _animate_attr(el_match_re, svg, anim_xml):
    """Insert anim_xml before the self-closing /> of each matching element,
    converting <tag .../> into <tag ...>anim</tag>."""
    def repl(m):
        tag = m.group(0)
        # turn '<circle .../>' into '<circle ...>{anim}</circle>'
        inner = tag[:-2].rstrip()  # drop '/>'
        tagname = re.match(r"<(\w+)", tag).group(1)
        return f"{inner}>{anim_xml}</{tagname}>"
    return re.sub(el_match_re, repl, svg)


def _shards(svg: str, rng: random.Random) -> str:
    # Body: fade up (cooling glass) via opacity animate
    body_anim = (
        '<animate attributeName="opacity" from="0" to="1" '
        'dur="2.6s" begin="0.3s" fill="freeze"/>'
    )
    svg = _animate_attr(r'<path class="shell-body"[^>]*/>', svg, body_anim)

    # Knots & jewels: fly in from a random offset + fade, via animateTransform
    def fly(cls, delay):
        def repl(m):
            tag = m.group(0)
            dx = rng.uniform(-200, 200)
            dy = rng.uniform(-200, 200)
            inner = tag[:-2].rstrip()
            anim = (
                f'<animateTransform attributeName="transform" type="translate" '
                f'from="{dx:.0f} {dy:.0f}" to="0 0" dur="2.4s" begin="{delay}s" '
                f'fill="freeze" calcMode="spline" keySplines="0.2 0.8 0.2 1" keyTimes="0;1"/>'
                f'<animate attributeName="opacity" from="0" to="{0.9 if cls=="shell-knot" else 0.95}" '
                f'dur="2.0s" begin="{delay}s" fill="freeze"/>'
            )
            return f"{inner}>{anim}</circle>"
        return repl
    svg = re.sub(r'<circle class="shell-knot"[^>]*/>', fly("shell-knot", 0.1), svg)
    svg = re.sub(r'<circle class="shell-jewel"[^>]*/>', fly("shell-jewel", 0.35), svg)

    # Aperture opens last
    svg = _aperture_open(svg, begin=1.2)
    return svg


def _draw(svg: str) -> str:
    # Centerline and rim: draw via stroke-dashoffset animation.
    # SMIL can animate stroke-dashoffset; we set a large dasharray inline.
    def draw_path(m):
        tag = m.group(0)
        inner = tag[:-2].rstrip()
        # add dasharray, animate dashoffset from big->0
        inner = inner.replace("<path", '<path stroke-dasharray="6000"', 1)
        anim = (
            '<animate attributeName="stroke-dashoffset" from="6000" to="0" '
            'dur="3.2s" begin="0.3s" fill="freeze"/>'
        )
        return f"{inner}>{anim}</path>"
    svg = re.sub(r'<path class="shell-centerline"[^>]*/>', draw_path, svg)
    svg = re.sub(r'<path class="shell-rim"[^>]*/>', draw_path, svg)

    # Body fades in behind the drawing line
    body_anim = (
        '<animate attributeName="opacity" from="0" to="1" '
        'dur="3.4s" begin="0.6s" fill="freeze"/>'
    )
    svg = _animate_attr(r'<path class="shell-body"[^>]*/>', svg, body_anim)

    # Knots/jewels bloom (scale 0->1) with staggered delays
    def bloom(delay):
        def repl(m):
            tag = m.group(0)
            inner = tag[:-2].rstrip()
            anim = (
                f'<animateTransform attributeName="transform" type="scale" '
                f'from="0" to="1" dur="0.6s" begin="{delay}s" fill="freeze" '
                f'additive="sum"/>'
                f'<animate attributeName="opacity" from="0" to="0.95" '
                f'dur="0.5s" begin="{delay}s" fill="freeze"/>'
            )
            return f"{inner}>{anim}</circle>"
        return repl
    # stagger by occurrence using incremental delays
    svg = _stagger_bloom(svg, "shell-knot", base=0.6, step=0.3)
    svg = _stagger_bloom(svg, "shell-jewel", base=1.0, step=0.2)

    svg = _aperture_open(svg, begin=1.8)
    return svg


def _glass(svg: str) -> str:
    # Body solidifies: opacity 0->1 (the saturate/blur part needs CSS filters,
    # which Gradio strips, so we approximate the "glass" feel with a staged
    # opacity + a brief over-bright flash via a second opacity pulse).
    body_anim = (
        '<animate attributeName="opacity" values="0;0.5;1" keyTimes="0;0.5;1" '
        'dur="3.4s" begin="0.3s" fill="freeze"/>'
    )
    svg = _animate_attr(r'<path class="shell-body"[^>]*/>', svg, body_anim)

    # Knots & jewels twinkle in
    twinkle = (
        '<animate attributeName="opacity" values="0;1" dur="2.4s" '
        'begin="1.0s" fill="freeze"/>'
    )
    svg = _animate_attr(r'<circle class="shell-knot"[^>]*/>', svg, twinkle)
    svg = _animate_attr(r'<circle class="shell-jewel"[^>]*/>', svg, twinkle)

    svg = _aperture_open(svg, begin=1.4)
    return svg


def _stagger_bloom(svg, cls, base, step):
    """Apply scale-bloom with incrementing delay to each element of class cls."""
    pattern = re.compile(rf'<circle class="{cls}"[^>]*/>')
    matches = list(pattern.finditer(svg))
    # process in reverse so indices stay valid
    for i in range(len(matches) - 1, -1, -1):
        m = matches[i]
        tag = m.group(0)
        delay = base + i * step
        inner = tag[:-2].rstrip()
        anim = (
            f'<animateTransform attributeName="transform" type="scale" '
            f'from="0" to="1" dur="0.6s" begin="{delay:.2f}s" fill="freeze" additive="sum"/>'
            f'<animate attributeName="opacity" from="0" to="0.95" '
            f'dur="0.5s" begin="{delay:.2f}s" fill="freeze"/>'
        )
        new = f"{inner}>{anim}</circle>"
        svg = svg[:m.start()] + new + svg[m.end():]
    return svg


def _aperture_open(svg: str, begin: float) -> str:
    """The breakthrough mouth opens last: scale + fade, frozen open."""
    def repl(m):
        tag = m.group(0)
        inner = tag[:-2].rstrip()
        anim = (
            f'<animate attributeName="opacity" from="0" to="0.95" '
            f'dur="0.8s" begin="{begin}s" fill="freeze"/>'
        )
        return f"{inner}>{anim}</ellipse>"
    return re.sub(r'<ellipse class="shell-aperture"[^>]*/>', repl, svg)


def animate_shell_svg(svg: str, seed=0, style: str | None = None) -> str:
    """Inject SMIL birth animation into a finished shell SVG. Survives Gradio
    HTML sanitization (SMIL is part of SVG, not CSS). Ends on the static shell.
    """
    rng = random.Random(seed)
    chosen = style or rng.choice(STYLES)
    if chosen == "shards":
        return _shards(svg, rng)
    if chosen == "draw":
        return _draw(svg)
    return _glass(svg)



REPLAY_HTML = """
<button id="replay-birth" title="watch the shell grow again">↻ watch it grow again</button>
<style>
#replay-birth{
  position:fixed;left:50%;bottom:10px;transform:translateX(-50%);
  z-index:9999;font:12px/1.2 Georgia,serif;font-style:italic;
  padding:6px 14px;border-radius:14px;cursor:pointer;
  background:rgba(20,16,12,0.55);color:#efe0b0;border:1px solid rgba(200,162,76,0.5);
  backdrop-filter:blur(2px);transition:opacity .3s;opacity:0.75;
}
#replay-birth:hover{opacity:1;background:rgba(20,16,12,0.75);}
</style>
<script>
(function(){
  function restart(){
    var svg = document.querySelector('svg');
    if(!svg) return;
    try { svg.setCurrentTime(0); } catch(e){}
    var anims = svg.querySelectorAll('animate, animateTransform, animateMotion');
    anims.forEach(function(a){ try { a.beginElement(); } catch(e){} });
  }
  var btn = document.getElementById('replay-birth');
  if(btn){ btn.addEventListener('click', restart); }
})();
</script>
"""


def inject_replay(iframe_inner_html: str) -> str:
    """Add a 'watch it grow again' button + restart JS inside the iframe doc."""
    if "</body>" in iframe_inner_html:
        return iframe_inner_html.replace("</body>", REPLAY_HTML + "</body>", 1)
    return iframe_inner_html + REPLAY_HTML


def wrap_in_iframe(animated_svg: str, height: int = 660) -> str:
    """Wrap an animated SVG in an <iframe srcdoc> so Gradio's HTML sanitizer
    cannot strip the SMIL animation. The iframe is an isolated document; its
    srcdoc contents render verbatim, animation intact.

    Gradio's gr.HTML sanitizes top-level <svg>/<animate>, but it does NOT parse
    into iframe srcdoc, so the animation survives.
    """
    import html as _html
    # The SVG becomes a full tiny HTML document inside the iframe
    doc = (
        "<!DOCTYPE html><html><head><style>"
        "html,body{margin:0;padding:0;background:transparent;overflow:hidden;"
        "height:100%;display:flex;align-items:center;justify-content:center}"
        "svg{max-width:100%;max-height:100%;width:auto;height:auto;display:block}"
        "</style></head><body>" + animated_svg + "</body></html>"
    )
    if DIAGNOSTIC:
        doc = inject_probe(doc)
    doc = inject_replay(doc)
    escaped = _html.escape(doc, quote=True)
    # The shell is square. Render the iframe as a centered square that fits the
    # column width but caps at `height`px tall, so the WHOLE shell shows (no
    # top/bottom clipping). max-width keeps it from ballooning on wide screens.
    return (
        f'<div style="display:flex;justify-content:center;width:100%;">'
        f'<iframe srcdoc="{escaped}" '
        f'style="width:{height}px;max-width:100%;height:{height}px;'
        f'border:none;background:transparent;" '
        f'sandbox="allow-scripts"></iframe>'
        f'</div>'
    )
