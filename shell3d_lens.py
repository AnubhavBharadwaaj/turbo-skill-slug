"""
Integration shim: exposes the 3D shell lens to the flat-imported app.

The SceneGraph package (scene_graph / scene_builder / renderer / renderers) uses
flat internal imports, so we add its directory to sys.path once and expose a
single clean entry point: render_shell_3d(extraction) -> iframe HTML (or None).

Degradation: any failure (missing module, bad extraction) returns None, and the
app shows nothing for the lens rather than breaking. This is the renderer
protocol's `available()` philosophy applied at the app boundary.
"""

from __future__ import annotations

import os
import sys

_SCENE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scenegraph")
if _SCENE_DIR not in sys.path:
    sys.path.insert(0, _SCENE_DIR)
_RENDERERS_DIR = os.path.join(_SCENE_DIR, "renderers")
if _RENDERERS_DIR not in sys.path:
    sys.path.insert(0, _RENDERERS_DIR)


def render_shell_3d(extraction: dict) -> str | None:
    """Build the SceneGraph and render the 3D iridescent shell lens. Returns iframe
    HTML, or None if anything is unavailable (the app degrades gracefully)."""
    try:
        from scene_builder import build_scene_graph
        from shell3d import Shell3DRenderer
        scene = build_scene_graph(extraction)
        renderer = Shell3DRenderer()
        ok, _reason = renderer.available()
        if not ok:
            return None
        out = renderer.render(scene)
        return out.get("html")
    except Exception:
        return None
