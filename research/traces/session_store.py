"""
Phase 2 (part 1): a store of past sessions' extractions, so the promotion engine
can look across sessions for recurring gotchas.

Deliberately simple and dependency-light: JSON on disk (or the Modal volume in
production). Each record is one session's extraction plus its id and timestamp.
"""

from __future__ import annotations

import json
import os
import time


class SessionStore:
    def __init__(self, path: str = "./session_store.json"):
        self.path = path
        self._data = {"sessions": []}
        self._load()

    def _load(self) -> None:
        if os.path.exists(self.path):
            try:
                with open(self.path) as f:
                    self._data = json.load(f)
            except Exception:
                self._data = {"sessions": []}

    def _save(self) -> None:
        tmp = self.path + ".tmp"
        with open(tmp, "w") as f:
            json.dump(self._data, f, indent=2)
        os.replace(tmp, self.path)

    def add(self, session_id: str, extraction: dict) -> None:
        # avoid duplicates by id
        if any(s["session_id"] == session_id for s in self._data["sessions"]):
            return
        self._data["sessions"].append({
            "session_id": session_id,
            "added_at": time.time(),
            "extraction": extraction,
        })
        self._save()

    def all(self) -> list:
        return list(self._data["sessions"])

    def count(self) -> int:
        return len(self._data["sessions"])

    def gotchas_with_source(self) -> list:
        """Flatten all gotchas across sessions, tagged with their source session_id."""
        out = []
        for s in self._data["sessions"]:
            for g in (s["extraction"].get("gotchas") or []):
                if isinstance(g, str) and g.strip():
                    out.append({"gotcha": g.strip(), "session_id": s["session_id"]})
        return out
