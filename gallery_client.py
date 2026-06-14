"""
Client for the shared shell gallery (talks to the Modal gallery endpoints).

Set the three endpoint URLs via env (printed when you `modal deploy
modal_gallery.py`), or they default to the conventional Modal URL shape for the
'slug-gallery' app under the known account.
"""

import os
import json

import httpx

_ACCOUNT = "anubhavbharadwaaj"
SAVE_URL = os.environ.get(
    "GALLERY_SAVE_URL", f"https://{_ACCOUNT}--slug-gallery-save.modal.run")
LIST_URL = os.environ.get(
    "GALLERY_LIST_URL", f"https://{_ACCOUNT}--slug-gallery-list-shells.modal.run")
SHELL_URL = os.environ.get(
    "GALLERY_SHELL_URL", f"https://{_ACCOUNT}--slug-gallery-shell.modal.run")

_TIMEOUT = 20


def save_shell(svg: str, meta: dict) -> str | None:
    """Save a shell to the shared gallery. Returns the new id, or None on failure."""
    try:
        r = httpx.post(SAVE_URL, json={"svg": svg, "meta": meta}, timeout=_TIMEOUT)
        r.raise_for_status()
        return r.json().get("id")
    except Exception:
        return None


def list_shells(limit: int = 60) -> list[dict]:
    """Newest-first metadata index. Empty list on failure."""
    try:
        r = httpx.get(LIST_URL, params={"limit": limit}, timeout=_TIMEOUT)
        r.raise_for_status()
        return r.json().get("shells", [])
    except Exception:
        return []


def get_shell(shell_id: str) -> dict | None:
    """One shell {svg, meta} by id. None on failure."""
    try:
        r = httpx.get(SHELL_URL, params={"id": shell_id}, timeout=_TIMEOUT)
        r.raise_for_status()
        data = r.json()
        return data if "svg" in data else None
    except Exception:
        return None
