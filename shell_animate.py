"""
Scroll-unroll birth animation for the shell.

The shell is born like an ancient scroll unfurling. A radial wipe mask reveals
the colored spiral from the eye outward — the scroll unrolling — led by a glowing
gold parchment edge. As the unrolling front passes each battle figure, that
figure inks in. The breakthrough dragon and aperture land last, at the tip.

Why a wipe MASK and not stroke-drawing: the shell body is a single filled spiral
path, so it cannot "draw" like a stroke. A growing radial mask genuinely reveals
the filled body progressively, which is what reads as a scroll unrolling.

SMIL (native SVG animation) so it survives Gradio's sanitizer; wrapped in an
<iframe srcdoc>. fill="freeze" holds the final static shell. Figures default
visible (animation drives them from opacity 0), so a no-SMIL browser still shows
the complete shell.
"""

from __future__ import annotations

import re

from anim_diagnostic import inject_probe

DIAGNOSTIC = False

SCROLL_DUR = 3.6          # seconds for the scroll to fully unroll
FIG_FADE = 0.7            # seconds each figure takes to ink in
EYE_X, EYE_Y = 320.0, 335.0   # shell eye (spiral origin); body starts here
MAX_R = 330.0            # radius that covers the whole 640 canvas from the eye
KEYSPLINE = "0.3 0 0.4 1"     # ease for the unroll


def _scroll_mask_and_edge(animated_only: bool = True) -> tuple[str, str]:
    """Return (mask_def, glowing_edge) for the live animated scroll-unroll."""
    mask_circle = (
        f'<circle cx="{EYE_X}" cy="{EYE_Y}" r="0" fill="white">'
        f'<animate attributeName="r" from="0" to="{MAX_R}" dur="{SCROLL_DUR}s" '
        f'begin="0s" fill="freeze" calcMode="spline" keySplines="{KEYSPLINE}" '
        f'keyTimes="0;1"/></circle>'
    )
    mask_def = f'<mask id="scrollWipe">{mask_circle}</mask>'
    edge = (
        f'<g class="scroll-edge">'
        f'<circle cx="{EYE_X}" cy="{EYE_Y}" r="0" fill="none" stroke="#e6c870" '
        f'stroke-width="6" opacity="0.55">'
        f'<animate attributeName="r" from="0" to="{MAX_R}" dur="{SCROLL_DUR}s" '
        f'begin="0s" fill="freeze" calcMode="spline" keySplines="{KEYSPLINE}" keyTimes="0;1"/>'
        f'<animate attributeName="opacity" values="0.55;0.55;0" keyTimes="0;0.82;1" '
        f'dur="{SCROLL_DUR}s" begin="0s" fill="freeze"/></circle>'
        f'<circle cx="{EYE_X}" cy="{EYE_Y}" r="0" fill="none" stroke="#efe0b0" '
        f'stroke-width="2" opacity="0.8">'
        f'<animate attributeName="r" from="0" to="{MAX_R}" dur="{SCROLL_DUR}s" '
        f'begin="0s" fill="freeze" calcMode="spline" keySplines="{KEYSPLINE}" keyTimes="0;1"/>'
        f'<animate attributeName="opacity" values="0.8;0.8;0" keyTimes="0;0.82;1" '
        f'dur="{SCROLL_DUR}s" begin="0s" fill="freeze"/></circle>'
        f'</g>'
    )
    return mask_def, edge


def _ink_figures(svg: str) -> str:
    """Each battle-fig group inks in (fade + slight rise) when the unrolling front
    reaches its data-pos radius. begin = pos * SCROLL_DUR (the dragon, pos==1.0,
    lands at the very end)."""
    def repl(m):
        tag = m.group(0)
        pos_match = re.search(r'data-pos="([\d.]+)"', tag)
        pos = float(pos_match.group(1)) if pos_match else 0.5
        begin = round(pos * SCROLL_DUR, 2)
        anim = (
            f'<animate attributeName="opacity" from="0" to="1" '
            f'dur="{FIG_FADE}s" begin="{begin}s" fill="freeze"/>'
            f'<animateTransform attributeName="transform" type="translate" '
            f'from="0 8" to="0 0" dur="{FIG_FADE}s" begin="{begin}s" '
            f'fill="freeze" calcMode="spline" keySplines="0.2 0.8 0.2 1" keyTimes="0;1"/>'
        )
        # do NOT hard-set opacity 0 (keeps figures visible if SMIL fails)
        return tag + anim
    return re.sub(r'<g class="battle-fig" data-pos="[\d.]+">', repl, svg)


def animate_shell_svg(svg: str, seed=0, style: str | None = None) -> str:
    """Inject the scroll-unroll birth: a radial wipe mask reveals the shell from
    the eye outward, a gold parchment edge rides the unrolling front, and the
    battle figures ink in as the front passes them.
    """
    # 1. inject the mask def + edge after </defs>
    defs_end = svg.find("</defs>")
    if defs_end == -1:
        open_end = svg.find(">", svg.find("<svg")) + 1
        svg = svg[:open_end] + "<defs></defs>" + svg[open_end:]
        defs_end = svg.find("</defs>")
    insert_at = defs_end + len("</defs>")
    mask_def, edge = _scroll_mask_and_edge()

    # 2. wrap the shell (from the body onward) in the masked group. Background
    #    (rect, atmosphere, particles, halos) stays unmasked so only the SHELL
    #    unrolls, against a steady night sky.
    body_idx = svg.find('<path class="shell-body"')
    if body_idx == -1:
        body_idx = insert_at  # fallback: mask everything after defs
    svg_close = svg.rfind("</svg>")

    head = svg[:insert_at] + mask_def
    pre_shell = svg[insert_at:body_idx]
    shell_region = svg[body_idx:svg_close]
    tail = svg[svg_close:]

    shell_region = _ink_figures(shell_region)

    return (
        head
        + pre_shell
        + '<g mask="url(#scrollWipe)">'
        + shell_region
        + '</g>'
        + edge
        + tail
    )


# ---- iframe wrapping (survives Gradio sanitizer) + replay button -------------

REPLAY_HTML = """
<button id="replay-birth" title="watch the scroll unroll again">\u21bb watch it unroll again</button>
<style>
#replay-birth{
  position:fixed;left:50%;bottom:10px;transform:translateX(-50%);
  z-index:9999;font:12px/1.2 Georgia,serif;font-style:italic;
  padding:6px 14px;border-radius:14px;cursor:pointer;
  background:rgba(20,16,12,0.55);color:#efe0b0;border:1px solid rgba(200,162,76,0.5);
  backdrop-filter:blur(2px);transition:opacity .3s;opacity:0.78;
}
#replay-birth:hover{opacity:1;background:rgba(20,16,12,0.75);}
</style>
<script>
(function(){
  function restart(){
    var svg = document.querySelector('svg');
    if(!svg) return;
    // Rewind the whole SVG timeline. For begin="0s" animations this re-runs
    // them from the top. We pause, seek to 0, then unpause so the flipbook
    // (stage opacity keyframes) and the curl motion both restart cleanly.
    try {
      svg.pauseAnimations();
      svg.setCurrentTime(0);
      svg.unpauseAnimations();
    } catch(e){
      // fallback: plain rewind
      try { svg.setCurrentTime(0); } catch(e2){}
    }
  }
  var btn = document.getElementById('replay-birth');
  if(btn){ btn.addEventListener('click', restart); }
})();
</script>
"""


def inject_replay(iframe_inner_html: str) -> str:
    if "</body>" in iframe_inner_html:
        return iframe_inner_html.replace("</body>", REPLAY_HTML + "</body>", 1)
    return iframe_inner_html + REPLAY_HTML


def wrap_in_iframe(animated_svg: str, height: int = 660, replay: bool = True) -> str:
    """Wrap the animated SVG in an <iframe srcdoc> (survives Gradio sanitizer),
    rendered as a centered square so the whole shell shows."""
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
    if replay:
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
