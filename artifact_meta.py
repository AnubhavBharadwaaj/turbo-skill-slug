"""
Phase 1: lifecycle metadata for every knowledge artifact the slug emits.

Grounded in arXiv:2604.15877 (Experience Compression Spectrum), which names
"continuous lifecycle governance" as a core design principle and "lifecycle
management remains an afterthought" as a key gap: every knowledge artifact should
carry metadata (provenance, confidence, usage frequency, last validation time)
enabling principled maintenance.

This module is pure data + helpers. Nothing here calls a model or renders anything.
It is the substrate Phase 2 (promotion/demotion) and Phase 3 (multi-analyst) build on.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field, asdict
from typing import Any

# Compression levels from the spectrum paper.
LEVEL_RAW = 0          # L0: raw transcript/trace
LEVEL_EPISODIC = 1     # L1: a single session's structured record
LEVEL_SKILL = 2        # L2: a transferable skill (one session)
LEVEL_RULE = 3         # L3: a declarative rule (promoted across sessions)

_LEVEL_NAME = {0: "raw", 1: "episodic", 2: "skill", 3: "rule"}


@dataclass
class ArtifactMeta:
    """Lifecycle metadata attached to any knowledge artifact (skill, rule, ...)."""
    level: int                              # 0..3 on the compression spectrum
    provenance: list = field(default_factory=list)   # source session_ids
    confidence: float = 0.0                 # 0..1, grows with corroborating evidence
    usage_count: int = 0                    # times retrieved/applied
    created_at: float = field(default_factory=time.time)
    last_validated: float | None = None     # last time it passed a held-out check
    status: str = "active"                  # active | deprecated | demoted
    notes: str = ""

    def level_name(self) -> str:
        return _LEVEL_NAME.get(self.level, str(self.level))

    def record_use(self) -> None:
        self.usage_count += 1

    def mark_validated(self) -> None:
        self.last_validated = time.time()

    def deprecate(self, reason: str = "") -> None:
        self.status = "deprecated"
        if reason:
            self.notes = (self.notes + f" | deprecated: {reason}").strip(" |")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @staticmethod
    def from_dict(d: dict) -> "ArtifactMeta":
        known = {k: d[k] for k in ArtifactMeta.__dataclass_fields__ if k in d}
        return ArtifactMeta(**known)


@dataclass
class Artifact:
    """A knowledge artifact (the content) plus its lifecycle metadata."""
    content: str
    meta: ArtifactMeta

    def to_dict(self) -> dict[str, Any]:
        return {"content": self.content, "meta": self.meta.to_dict()}

    @staticmethod
    def from_dict(d: dict) -> "Artifact":
        return Artifact(content=d.get("content", ""),
                        meta=ArtifactMeta.from_dict(d.get("meta", {})))


def confidence_from_evidence(n_sessions: int, k_threshold: int) -> float:
    """A simple, honest confidence: saturating in the number of corroborating
    sessions, normalized so reaching the promotion threshold ~= 0.6, and more
    evidence pushes toward 1.0. Deliberately not over-engineered."""
    if n_sessions <= 0:
        return 0.0
    base = min(1.0, n_sessions / max(1, k_threshold))   # hits 1.0 at threshold
    # soften so threshold is 0.6 not 1.0, leaving headroom for more evidence
    return round(min(1.0, 0.6 * base + 0.1 * max(0, n_sessions - k_threshold)), 3)
