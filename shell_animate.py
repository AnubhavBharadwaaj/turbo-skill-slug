"""
Scroll-unroll birth animation for the shell.

The shell is born like a scroll unrolling: the spiral draws itself from the eye
outward, and as the unrolling "reaches" each position, the byobu battle figures
get inked onto it in sequence, like a narrative being painted across a folding
screen. The breakthrough dragon is the last thing to appear, at the tip.

Implemented with SMIL (native SVG animation) so it survives Gradio's HTML
sanitizer, wrapped in an <iframe srcdoc> so even the sanitizer's outer pass
cannot strip it. fill="freeze" holds the final static shell.

Timing model (total ~ SCROLL_DUR + a beat):
  0.0s ............................. spiral begins unrolling from the eye
  0.0 .. SCROLL_DUR ................ spiral draws outward; figures ink in at
                                     begin = pos * SCROLL_DUR (synced to the
                                     unrolling front passing each figure)
  SCROLL_DUR + .. ................. dragon + aperture settle
"""

from __future__ import annotations

import re

from anim_diagnostic import inject_probe

# Set False for final submission; True shows a live badge reporting whether the
# SMIL animation is present and actually running inside the iframe.
DIAGNOSTIC = False

SCROLL_DUR = 3.2          # seconds for the spiral to fully unroll
FIG_FADE = 0.7            # seconds each figure takes to ink in
DRAGON_EXTRA = 0.5        # the dragon lands a beat after the scroll completes


def _animate_spiral_draw(svg: str) -> str:
    """Make the centerline + rim draw themselves outward (the scroll unrolling)."""
    def draw_path(m):
        tag = m.group(0)
        inner = tag[:-2].rstrip() if tag.endswith("/>") else tag
        # large dasharray so the whole path is initially "undrawn"
        inner = inner.replace("<path", '<path stroke-dasharray="7000"', 1)
        anim = (
            f'<animate attributeName="stroke-dashoffset" from="7000" to="0" '
            f'dur="{SCROLL_DUR}s" begin="0s" fill="freeze"/>'
        )
        return f"{inner}>{anim}</path>"
    svg = re.sub(r'<path class="shell-centerline"[^>]*/>', draw_path, svg)
    svg = re.sub(r'<path class="shell-rim"[^>]*/>', draw_path, svg)
    return svg


def _animate_body_unfurl(svg: str) -> str:
    """The shell body fades up as the scroll unrolls (the parchment appearing)."""
    def repl(m):
        tag = m.group(0)
        inner = tag[:-2].rstrip() if tag.endswith("/>") else tag
        anim = (
            f'<animate attributeName="opacity" from="0" to="1" '
            f'dur="{SCROLL_DUR}s" begin="0s" fill="freeze"/>'
        )
        return f"{inner}>{anim}</path>"
    return re.sub(r'<path class="shell-body"[^>]*/>', repl, svg, count=1)


def _ink_figures(svg: str) -> str:
    """Each battle-fig group inks in (fade + slight rise) when the unrolling front
    reaches its data-pos. begin = pos * SCROLL_DUR."""
    def repl(m):
        tag = m.group(0)  # the opening <g class="battle-fig" data-pos="X">
        pos_match = re.search(r'data-pos="([\d.]+)"', tag)
        pos = float(pos_match.group(1)) if pos_match else 0.5
        begin = round(pos * SCROLL_DUR, 2)
        # the dragon (pos==1.0) gets a small extra beat so it lands last
        if pos >= 0.999:
            begin = round(SCROLL_DUR + DRAGON_EXTRA, 2)
        anim = (
            f'<animate attributeName="opacity" from="0" to="1" '
            f'dur="{FIG_FADE}s" begin="{begin}s" fill="freeze"/>'
            f'<animateTransform attributeName="transform" type="translate" '
            f'from="0 10" to="0 0" dur="{FIG_FADE}s" begin="{begin}s" '
            f'fill="freeze" calcMode="spline" keySplines="0.2 0.8 0.2 1" keyTimes="0;1"/>'
        )
        # Inject the anim right after the tag. We do NOT hard-set opacity="0" on
        # the group as a static attribute: if a browser failed to run SMIL, that
        # would leave the figure invisible (worse than no animation). The
        # <animate from="0"> drives the ink-in; freeze holds it; and a no-SMIL
        # browser simply shows the figure at its natural opacity.
        return tag + anim
    return re.sub(r'<g class="battle-fig" data-pos="[\d.]+">', repl, svg)


def _animate_aperture(svg: str) -> str:
    """The breakthrough aperture opens last, with the dragon."""
    def repl(m):
        tag = m.group(0)
        inner = tag[:-2].rstrip() if tag.endswith("/>") else tag
        begin = round(SCROLL_DUR + DRAGON_EXTRA, 2)
        anim = (
            f'<animate attributeName="opacity" from="0" to="0.95" '
            f'dur="0.9s" begin="{begin}s" fill="freeze"/>'
        )
        return f"{inner}>{anim}</ellipse>"
    return re.sub(r'<ellipse class="shell-aperture"[^>]*/>', repl, svg)


def animate_shell_svg(svg: str, seed=0, style: str | None = None) -> str:
    """Inject the scroll-unroll birth animation. `style`/`seed` kept for API
    compatibility; there is now one cohesive narrative animation."""
    svg = _animate_body_unfurl(svg)
    svg = _animate_spiral_draw(svg)
    svg = _ink_figures(svg)
    svg = _animate_aperture(svg)
    return svg


# ---- iframe wrapping (survives Gradio sanitizer) + replay button -------------

REPLAY_HTML = """
<button id="replay-birth" title="watch the shell grow again">\u21bb watch it grow again</button>
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
    """Wrap the animated SVG in an <iframe srcdoc> so Gradio's HTML sanitizer
    cannot strip the SMIL animation. Rendered as a centered square so the WHOLE
    shell shows (no top/bottom clipping)."""
    import html as _html
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
    return (
        f'<div style="display:flex;justify-content:center;width:100%;">'
        f'<iframe srcdoc="{escaped}" '
        f'style="width:{height}px;max-width:100%;height:{height}px;'
        f'border:none;background:transparent;" '
        f'sandbox="allow-scripts"></iframe>'
        f'</div>'
    )
