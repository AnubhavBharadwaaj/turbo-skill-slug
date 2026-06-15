"""Pure-regex session genre detection for TurboSkillSlug."""

from __future__ import annotations

import re


GENRES = ("debugging", "exploration", "authoring", "feature", "refactor", "setup")

_PATTERNS = {
    "debugging": (
        r"\b(debug|bug|fix|error|traceback|exception|fail(?:ed|ing)?|broken|crash|"
        r"regression|why.*not|doesn't work|not working|stuck|issue)\b",
    ),
    "exploration": (
        r"\b(explore|understand|inspect|go through|read through|map out|figure out|"
        r"investigate|familiarize|what does|how does|codebase|repo)\b",
    ),
    "authoring": (
        r"\b(write|draft|document|readme|docs|blog|article|copy|proposal|report|"
        r"build log|submission|explain|summarize)\b",
    ),
    "feature": (
        r"\b(add|implement|wire|build|create|ship|feature|endpoint|button|ui|"
        r"component|integrate)\b",
    ),
    "refactor": (
        r"\b(refactor|cleanup|clean up|reorganize|simplify|rename|dedupe|extract "
        r"helper|move .* into)\b",
    ),
    "setup": (
        r"\b(set ?up|install|configure|config|dependency|requirements|deploy|"
        r"environment|env var|ci|workflow|initialize|scaffold)\b",
    ),
}

_FRAMES = {
    "debugging": (
        "Witness the struggle: the failed approaches, the exact symptoms, the "
        "turning point, and what finally fixed the problem."
    ),
    "exploration": (
        "Witness the discoveries: the non-obvious facts learned about the "
        "codebase, the map that emerged, and the clearest insight."
    ),
    "authoring": (
        "Witness the decisions: what was clarified, what false assumptions were "
        "caught, and what document or explanation was delivered."
    ),
    "feature": (
        "Witness what was built: the new behavior, the integration points, the "
        "naive paths that would break, and the delivered feature."
    ),
    "refactor": (
        "Witness the reshaping: what moved, what got simpler, what invariants "
        "had to hold, and what could have broken."
    ),
    "setup": (
        "Witness the setup path: the configuration choices, dependency traps, "
        "environment gotchas, and the final working baseline."
    ),
}

_LEGENDS = {
    "debugging": {
        "knot": "dead ends and failed approaches",
        "jewel": "verification gotchas",
        "aperture": "the breakthrough that fixed it",
    },
    "exploration": {
        "knot": "confusions or branches that did not explain the system",
        "jewel": "discoveries about the codebase",
        "aperture": "the clearest insight",
    },
    "authoring": {
        "knot": "false assumptions caught",
        "jewel": "decisions worth preserving",
        "aperture": "the document delivered",
    },
    "feature": {
        "knot": "implementation paths that would break",
        "jewel": "integration gotchas",
        "aperture": "the feature working",
    },
    "refactor": {
        "knot": "risky seams and avoided regressions",
        "jewel": "invariants worth remembering",
        "aperture": "the simpler shape that remained",
    },
    "setup": {
        "knot": "environment traps",
        "jewel": "configuration details worth saving",
        "aperture": "the working baseline",
    },
}


def detect_genre(first_instruction: str, transcript: str = "") -> str:
    """Detect the session genre with deterministic regex scoring."""
    text = f"{first_instruction}\n{transcript[:3000]}".lower()
    scores = {genre: 0 for genre in GENRES}
    for genre, patterns in _PATTERNS.items():
        for pattern in patterns:
            scores[genre] += len(re.findall(pattern, text, re.IGNORECASE))

    # First instruction is more predictive than the full transcript.
    first = first_instruction.lower()
    for genre, patterns in _PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, first, re.IGNORECASE):
                scores[genre] += 3

    best = max(GENRES, key=lambda genre: (scores[genre], -GENRES.index(genre)))
    return best if scores[best] > 0 else "feature"


def frame_for(genre: str) -> str:
    """Return the witness frame for a genre."""
    return _FRAMES.get(genre, _FRAMES["feature"])


def shell_legend(genre: str) -> dict[str, str]:
    """Return genre-specific meanings for shell features."""
    return dict(_LEGENDS.get(genre, _LEGENDS["feature"]))
