"""
Browser-rendered birth animations for the shell.

The shell is generated once as a static SVG. This module injects a CSS
animation that the BROWSER plays at 60fps, so the shell appears to come into
being smoothly rather than in mechanical server-streamed frames.

Three styles, chosen randomly per shell (seeded by the session so it is
deterministic per shell):

  1. "shards"   - knots and jewels scatter in from random directions, fly to
                  position, and crystallize; the body fades up like cooling glass.
  2. "draw"     - the spiral draws itself from the center outward (stroke
                  dashoffset), and knots/jewels bloom in sequence as the line
                  passes them.
  3. "glass"    - the whole shell glows as translucent saturated stained glass,
                  then solidifies into the nacre body.

Usage:
  from shell_animate import animate_shell_svg
  animated = animate_shell_svg(static_svg, seed=hash(...) )
"""

from __future__ import annotations

import random
import re


STYLES = ("shards", "draw", "glass")


def pick_style(seed) -> str:
    rng = random.Random(seed)
    return rng.choice(STYLES)


# --- per-style CSS -------------------------------------------------------

def _css_shards(rng: random.Random) -> str:
    """Knots & jewels fly in from scattered offsets and crystallize."""
    # Each knot/jewel gets a CSS var for its incoming offset, set inline below.
    return """
    @keyframes shell-body-cool {
      0%   { opacity: 0; filter: saturate(2.2) brightness(1.5); }
      60%  { opacity: 0.85; }
      100% { opacity: 1; filter: none; }
    }
    @keyframes shard-fly {
      0%   { opacity: 0; transform: translate(var(--dx,0px), var(--dy,0px)) scale(0.2) rotate(var(--dr,0deg)); }
      70%  { opacity: 1; }
      100% { opacity: 1; transform: translate(0,0) scale(1) rotate(0deg); }
    }
    @keyframes aperture-open {
      0%, 60% { opacity: 0; transform: scale(0.3); }
      100%    { opacity: 0.95; transform: scale(1); }
    }
    .shell-body { animation: shell-body-cool 1.6s ease-out both; }
    .shell-knot, .shell-jewel {
      transform-box: fill-box; transform-origin: center;
      animation: shard-fly 1.4s cubic-bezier(.2,.8,.2,1) both;
    }
    .shell-jewel { animation-delay: .25s; }
    .shell-aperture {
      transform-box: fill-box; transform-origin: center;
      animation: aperture-open 2.0s ease-out both;
    }
    """


def _css_draw() -> str:
    """Spiral draws itself; knots/jewels bloom as the line passes."""
    return """
    @keyframes draw-line {
      0%   { stroke-dashoffset: var(--len, 4000); opacity: 0.5; }
      100% { stroke-dashoffset: 0; opacity: 1; }
    }
    @keyframes body-fill {
      0%   { opacity: 0; }
      40%  { opacity: 0; }
      100% { opacity: 1; }
    }
    @keyframes bloom {
      0%   { opacity: 0; transform: scale(0); }
      100% { opacity: 1; transform: scale(1); }
    }
    @keyframes aperture-open {
      0%, 70% { opacity: 0; transform: scale(0.3); }
      100%    { opacity: 0.95; transform: scale(1); }
    }
    .shell-body { animation: body-fill 1.8s ease-in both; }
    .shell-centerline, .shell-rim {
      stroke-dasharray: var(--len, 4000);
      animation: draw-line 1.8s ease-out both;
    }
    .shell-knot, .shell-jewel {
      transform-box: fill-box; transform-origin: center;
      animation: bloom .7s ease-out both;
    }
    /* stagger blooms across the draw */
    .shell-knot:nth-of-type(1){animation-delay:.5s}
    .shell-knot:nth-of-type(2){animation-delay:.8s}
    .shell-knot:nth-of-type(3){animation-delay:1.1s}
    .shell-knot:nth-of-type(4){animation-delay:1.3s}
    .shell-jewel:nth-of-type(odd){animation-delay:1.0s}
    .shell-jewel:nth-of-type(even){animation-delay:1.3s}
    .shell-aperture {
      transform-box: fill-box; transform-origin: center;
      animation: aperture-open 2.2s ease-out both;
    }
    """


def _css_glass() -> str:
    """Whole shell glows as translucent stained glass, then solidifies."""
    return """
    @keyframes glass-solidify {
      0%   { opacity: 0; filter: saturate(2.6) brightness(1.6) blur(2px); }
      45%  { opacity: 0.7; filter: saturate(2.0) brightness(1.3) blur(1px); }
      100% { opacity: 1; filter: none; }
    }
    @keyframes glass-twinkle {
      0%   { opacity: 0; }
      50%  { opacity: 1; }
      100% { opacity: 1; }
    }
    @keyframes aperture-open {
      0%, 55% { opacity: 0; transform: scale(0.4); }
      100%    { opacity: 0.95; transform: scale(1); }
    }
    .shell-body { animation: glass-solidify 2.0s ease-out both; }
    .shell-knot { animation: glass-twinkle 1.6s ease-out both; animation-delay:.4s; }
    .shell-jewel { animation: glass-twinkle 1.6s ease-out both; animation-delay:.7s; }
    .shell-aperture {
      transform-box: fill-box; transform-origin: center;
      animation: aperture-open 2.2s ease-out both;
    }
    """


def _inject_shard_offsets(svg: str, rng: random.Random) -> str:
    """Give each knot/jewel a random incoming offset via inline style vars."""
    def add_offset(m):
        tag = m.group(0)
        dx = rng.uniform(-220, 220)
        dy = rng.uniform(-220, 220)
        dr = rng.uniform(-180, 180)
        style = f'style="--dx:{dx:.0f}px;--dy:{dy:.0f}px;--dr:{dr:.0f}deg"'
        # insert style before the closing />
        return tag[:-2] + f' {style}/>'
    svg = re.sub(r'<circle class="shell-knot"[^>]*/>', add_offset, svg)
    svg = re.sub(r'<circle class="shell-jewel"[^>]*/>', add_offset, svg)
    return svg


def animate_shell_svg(svg: str, seed=0, style: str | None = None) -> str:
    """Wrap a finished shell SVG with a browser-played birth animation.

    Returns the SVG with an injected <style> block (and, for shards, per-element
    offsets). The animation plays once on render; the final frame is the exact
    static shell, so nothing is lost if animations are disabled.
    """
    rng = random.Random(seed)
    chosen = style or rng.choice(STYLES)

    if chosen == "shards":
        css = _css_shards(rng)
        svg = _inject_shard_offsets(svg, rng)
    elif chosen == "draw":
        css = _css_draw()
    else:
        css = _css_glass()

    style_block = f'<style>\n{css}\n</style>'
    # Insert the style block right after the opening <svg ...> tag
    insert_at = svg.find(">", svg.find("<svg")) + 1
    return svg[:insert_at] + "\n" + style_block + svg[insert_at:]
