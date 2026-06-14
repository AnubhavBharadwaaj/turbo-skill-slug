"""
Renderer protocol: the interface every lens implements over a SceneGraph.

Each lens (character, shell3d, atmosphere, diorama) is a Renderer. The app shows
the available lenses at upload time, the user picks one (or "all"), and the chosen
renderer(s) consume the SAME SceneGraph. Renderers are independent and degradable:
`available()` lets a renderer declare itself unavailable (e.g. a hosted generation
key is missing, or WebGL is unsupported) without breaking the others.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from scene_graph import SceneGraph, SCHEMA_VERSION


@runtime_checkable
class Renderer(Protocol):
    # stable id used in the lens picker and for routing
    id: str
    # human label + one-line description for the picker
    label: str
    description: str
    # which SceneGraph schema versions this renderer supports
    supported_versions: tuple[str, ...]
    # does this renderer need a hosted/generation dependency?
    requires_generation: bool

    def available(self) -> tuple[bool, str]:
        """Return (is_available, reason). reason is shown if unavailable, e.g.
        'set REPLICATE_API_TOKEN to enable the painted atmosphere lens'."""
        ...

    def render(self, scene: SceneGraph) -> dict:
        """Produce the renderable output for this lens.

        Returns a dict the app knows how to display, e.g.:
          {"kind": "iframe", "html": "..."}        # 3D / character / canvas
          {"kind": "image", "url": "..."}          # generated atmosphere
          {"kind": "composite", "layers": [...]}   # the diorama
        Renderers NEVER raise for an empty/odd scene; they degrade to a sensible
        minimal output and note it in the returned dict under "notes".
        """
        ...


def supports(renderer: "Renderer", scene: SceneGraph) -> bool:
    return scene.schema_version in renderer.supported_versions


class LensRegistry:
    """Holds the available lenses and resolves which to offer at upload time."""

    def __init__(self) -> None:
        self._lenses: list[Renderer] = []

    def register(self, renderer: "Renderer") -> None:
        self._lenses.append(renderer)

    def all(self) -> list["Renderer"]:
        return list(self._lenses)

    def offerable(self, scene_version: str = SCHEMA_VERSION) -> list[dict]:
        """The lens picker payload: every lens with its availability, so the UI can
        show enabled/disabled states with reasons."""
        out = []
        for r in self._lenses:
            ok, reason = r.available()
            out.append({
                "id": r.id, "label": r.label, "description": r.description,
                "requires_generation": r.requires_generation,
                "version_ok": scene_version in r.supported_versions,
                "available": ok and (scene_version in r.supported_versions),
                "reason": reason if not ok else "",
            })
        return out
