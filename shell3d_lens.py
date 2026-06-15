"""
Integration shim: exposes the 3D shell lens to the flat-imported app.

Robust to layout: the scenegraph modules (scene_graph / scene_builder / renderer /
shell3d) may live in a scenegraph/ subfolder OR be flattened to the repo root by the
deploy. We add BOTH this file's directory and a scenegraph/ subdir (if present) to
sys.path, then import by module name. Exposes one entry point:
    render_shell_3d(extraction) -> iframe HTML, or None (graceful degradation).
"""

from __future__ import annotations

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
# add the repo root (files may be flattened here) ...
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
# ... and a scenegraph/ subfolder if it exists (files may be nested there)
_SUB = os.path.join(_HERE, "scenegraph")
if os.path.isdir(_SUB) and _SUB not in sys.path:
    sys.path.insert(0, _SUB)
_SUBREND = os.path.join(_SUB, "renderers")
if os.path.isdir(_SUBREND) and _SUBREND not in sys.path:
    sys.path.insert(0, _SUBREND)


def render_shell_3d(extraction: dict) -> str | None:
    """Build the SceneGraph and render the 3D iridescent shell. Returns iframe HTML,
    or None if anything is unavailable (the app degrades gracefully)."""
    try:
        from scene_builder import build_scene_graph
        from shell3d import Shell3DRenderer
    except Exception:
        return None
    try:
        scene = build_scene_graph(extraction)
        renderer = Shell3DRenderer()
        ok, _reason = renderer.available()
        if not ok:
            return None
        out = renderer.render(scene)
        return out.get("html")
    except Exception:
        return None
