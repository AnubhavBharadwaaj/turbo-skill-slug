"""
Read SWE-chat transcripts (Codex/Claude type/payload schema) and run Phases 1-3.

Precise schema (confirmed from real files):
  Each line: {"timestamp":..., "type": <event>, "payload": {...}}
  Content-bearing:
    response_item / type=message       -> content: [{type, text}] blocks
    response_item / type=function_call -> name + arguments (commands run)
    response_item / type=function_call_output|tool_result -> output/result
    event_msg     / type=user_message|agent_message       -> message / text
  Skip: session_meta, turn_context, token_count, task_started, reasoning(encrypted),
        and permission/environment boilerplate.

Run locally:
    export OPENROUTER_API_KEY=sk-or-...
    # free check first (no model calls) — confirms the reader pulls real content:
    python run_swe_chat_phases_v2.py --manifest ./swe_chat_traces/_manifest.txt --peek
    # then the real run:
    python run_swe_chat_phases_v2.py --manifest ./swe_chat_traces/_manifest.txt --k 2
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, "..", ".."))
sys.path.insert(0, SCRIPT_DIR)
sys.path.insert(1, REPO_ROOT)

_SKIP_EVENT_TYPES = {"token_count", "task_started", "task_complete", "turn_aborted"}
_BOILERPLATE_PREFIXES = ("<permissions", "<environment_context", "<user_instructions")


def _blocks_text(content) -> str:
    """A message 'content' is a list of typed blocks; pull text from each."""
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""
    out = []
    for b in content:
        if isinstance(b, dict):
            t = b.get("text") or b.get("content")
            if isinstance(t, str) and t.strip():
                out.append(t.strip())
        elif isinstance(b, str) and b.strip():
            out.append(b.strip())
    return " ".join(out)


def _line_text(obj) -> str:
    """Return a readable '[tag] text' line for one transcript event, or '' to skip."""
    etype = obj.get("type", "")
    p = obj.get("payload", {})
    if not isinstance(p, dict):
        return ""
    ptype = p.get("type", "")

    if etype in ("session_meta", "turn_context"):
        return ""

    if etype == "response_item":
        if ptype == "message":
            role = p.get("role", "")
            txt = _blocks_text(p.get("content"))
            if txt and not txt.startswith(_BOILERPLATE_PREFIXES):
                return f"[{role}] {txt}"
            return ""
        if ptype == "function_call":
            name = p.get("name", "tool")
            args = p.get("arguments", "")
            return f"[run:{name}] {args}" if args else ""
        if ptype in ("function_call_output", "custom_tool_call_output", "tool_result"):
            out = p.get("output") or p.get("result") or p.get("content")
            out = out if isinstance(out, str) else _blocks_text(out)
            return f"[output] {out}" if out else ""
        if ptype == "reasoning":
            return ""   # encrypted/empty
        return ""

    if etype == "event_msg":
        if ptype in _SKIP_EVENT_TYPES:
            return ""
        msg = p.get("message") or p.get("text")
        if isinstance(msg, str) and msg.strip() and not msg.startswith(_BOILERPLATE_PREFIXES):
            return f"[{ptype}] {msg}"
        return ""

    return ""


def read_transcript(path: str, max_chars: int = 14000) -> str:
    pieces = []
    try:
        with open(path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except Exception:
                    continue
                s = _line_text(obj)
                if s and len(s) > 4:
                    pieces.append(s[:800])
    except Exception as e:
        return f"(could not read {path}: {e})"
    return "\n".join(pieces)[:max_chars]


def is_review_session(path: str) -> bool:
    """True if this is a code-review session (no debugging arc to extract)."""
    try:
        with open(path) as f:
            for _ in range(8):
                line = f.readline()
                if not line:
                    break
                try:
                    obj = json.loads(line)
                except Exception:
                    continue
                p = obj.get("payload", {}) or {}
                if obj.get("type") == "session_meta":
                    sub = str(((p.get("source") or {}).get("subagent") or "")).lower()
                    if "review" in sub:
                        return True
                if p.get("type") == "user_message":
                    m = str(p.get("message", "")).lower()
                    if "review the current code changes" in m or "prioritized findings" in m:
                        return True
    except Exception:
        pass
    return False


def extract_one(trace_text: str, completer) -> dict:
    schema_hint = (
        "Extract a JSON record of this coding session with keys: "
        "themes (list), approaches_tried (list of {approach, why_it_failed}), "
        "dead_ends (list of {position 0-1, what_happened}), "
        "breakthroughs (list of {position 0-1, what_worked}), "
        "gotchas (list of short, SPECIFIC, non-obvious transferable traps), "
        "sentiment_arc ({start, end}). Only include gotchas genuinely supported by the "
        "trace; do NOT invent generic advice. Output ONLY the JSON."
    )
    raw = completer(f"{schema_hint}\n\nSESSION:\n{trace_text}\n\nJSON:")
    try:
        import re
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        return json.loads(m.group(0)) if m else {}
    except Exception:
        return {}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest")
    ap.add_argument("--in", dest="manifest_in")
    ap.add_argument("--out", default="swe_chat_sample_extractions.json")
    ap.add_argument("--k", type=int, default=2)
    ap.add_argument("--peek", action="store_true",
                    help="print char counts + sample text, NO model calls (free check)")
    args = ap.parse_args()

    manifest = args.manifest or args.manifest_in
    if not manifest:
        ap.error("one of --manifest or --in is required")

    with open(manifest) as f:
        paths = [ln.strip() for ln in f if ln.strip()]
    print(f"Reading {len(paths)} transcripts ...")

    if args.peek:
        for p in paths:
            review = is_review_session(p)
            t = read_transcript(p)
            tag = "  [REVIEW - would skip]" if review else ""
            print(f"\n=== {os.path.basename(p)}  chars={len(t)}{tag} ===")
            print(t[:700])
        return

    from openrouter_client import make_completer, DEFAULT_ANSWERER_MODEL
    from session_store import SessionStore
    from gotcha_cluster import cluster_by_judge
    from promotion_engine import promote
    from rule_phrasing import to_negative_constraint_llm
    completer = make_completer(DEFAULT_ANSWERER_MODEL, temperature=0.2, max_tokens=700)

    extractions = {}
    for p in paths:
        if is_review_session(p):
            print(f"  {os.path.basename(p)[:20]:20s} [REVIEW - skipped]")
            continue
        sid = os.path.splitext(os.path.basename(p))[0]
        trace = read_transcript(p)
        ex = extract_one(trace, completer)
        extractions[sid] = ex
        print(f"  {sid[:20]:20s} chars={len(trace):6d} gotchas={len(ex.get('gotchas', []))} "
              f"themes={ex.get('themes', [])[:2]}")

    total = sum(len(e.get("gotchas", [])) for e in extractions.values())
    print(f"\nTotal gotchas from {len(extractions)} debugging sessions: {total}")

    def same_gotcha(a, b):
        r = completer("Do these two engineering gotchas describe the SAME underlying "
                      "lesson? Answer ONLY 'yes' or 'no'.\n\nA: " + a + "\nB: " + b +
                      "\n\nAnswer:").strip().lower()
        return r.startswith("y")

    tmp = tempfile.mktemp(suffix=".json")
    store = SessionStore(tmp)
    for sid, ex in extractions.items():
        store.add(sid, ex)

    promoted = promote(store, k_threshold=args.k,
                       cluster_fn=lambda it: cluster_by_judge(it, same_gotcha),
                       reshape_fn=lambda g: to_negative_constraint_llm(g, completer),
                       validate_fn=lambda r, c: len(r) > 15)

    print("\n========== REAL-DATA RESULT ==========")
    print(f"debugging_sessions={len(extractions)} total_gotchas={total} "
          f"promoted={len(promoted)} (k>={args.k})")
    for a in promoted:
        print(f"  conf={a.meta.confidence} from {len(a.meta.provenance)} sessions")
        print(f"  rule: {a.content}")
    if not promoted:
        print("  (no promotion - read the saved extractions: were gotchas real but varied?)")

    out = args.out
    if not os.path.isabs(out):
        out = os.path.join(SCRIPT_DIR, out)
    with open(out, "w") as f:
        json.dump(extractions, f, indent=2)
    print(f"\nRaw extractions saved: {out}  - READ THEM (specific/real vs generic filler?).")
    os.remove(tmp)


if __name__ == "__main__":
    main()
