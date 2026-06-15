"""
Pull nebius/SWE-agent-trajectories (REAL GitHub-issue fixes) and run Phases 1-3.

Schema (verified from the dataset card, not guessed):
  parquet, columns: instance_id (str, '<repo>__<name>-<issue>'), model_name,
  target (bool: issue resolved?), trajectory (JSON STRING -> list of {role, ...}
  with role in system|ai|user), exit_status, generated_patch, eval_logs.

Why this fits promotion where SWE-chat didn't:
  - Every trajectory is a real bug FIX (struggle -> resolve), so gotchas exist.
  - instance_id encodes the repo, so we can group SAME-REPO trajectories, where the
    same library/codebase trap actually recurs across sessions -> promotion can fire.
  - target gives the success/failure label for the error vs success analyst split.

Run locally:
    pip install datasets
    export OPENROUTER_API_KEY=sk-or-...
    # default: pull trajectories concentrated on few repos (better for promotion)
    python nebius_loader.py --n 12 --k 2
    # free check, no model calls:
    python nebius_loader.py --n 12 --peek
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from collections import defaultdict

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, "..", ".."))
sys.path.insert(0, SCRIPT_DIR)
sys.path.insert(1, REPO_ROOT)


def _repo_of(instance_id: str) -> str:
    """'AnalogJ__lexicon-336' -> 'AnalogJ/lexicon'."""
    base = instance_id.rsplit("-", 1)[0]          # drop the issue number
    return base.replace("__", "/", 1)


def _traj_to_text(trajectory_field, max_chars: int = 14000) -> str:
    """trajectory is a JSON string (or already a list) of {role, ...} entries.
    role 'ai' = model reasoning/action, 'user' = environment observation,
    'system' = the harness prompt (skip). Flatten to readable text."""
    traj = trajectory_field
    if isinstance(traj, str):
        try:
            traj = json.loads(traj)
        except Exception:
            return traj[:max_chars]
    if not isinstance(traj, list):
        return str(traj)[:max_chars]

    pieces = []
    for step in traj:
        if not isinstance(step, dict):
            continue
        role = step.get("role", "")
        if role == "system":
            continue
        # content can be under 'content', 'thought'+'action', or 'system_prompt'
        content = step.get("content") or step.get("text")
        if content is None:
            # swe-agent style: thought + action, or observation
            content = " ".join(
                str(step.get(k, "")) for k in ("thought", "action", "observation")
                if step.get(k)
            )
        if isinstance(content, list):
            content = " ".join(
                (c.get("text") or "") if isinstance(c, dict) else str(c) for c in content
            )
        content = str(content).strip()
        if content:
            tag = {"ai": "agent", "user": "env"}.get(role, role)
            pieces.append(f"[{tag}] {content[:700]}")
    return "\n".join(pieces)[:max_chars]


def load_same_repo_sessions(n: int):
    """Stream the dataset and gather trajectories, PREFERRING repos that appear
    multiple times (so promotion has same-repo recurrence to find). Returns
    [{session_id, repo, trace, success}]."""
    from datasets import load_dataset
    ds = load_dataset("nebius/SWE-agent-trajectories", split="train", streaming=True)

    by_repo = defaultdict(list)
    seen_instances = set()
    scanned = 0
    # scan a window, bucket by repo, stop when some repo has >=2 and we have enough
    for row in ds:
        scanned += 1
        iid = row.get("instance_id", f"row{scanned}")
        repo = _repo_of(iid)
        # dedup: take at most a few trajectories per instance to get variety
        key = (iid, row.get("model_name", ""))
        if key in seen_instances:
            continue
        seen_instances.add(key)
        by_repo[repo].append(row)
        # stop once we can fill n from repos that have multiple sessions
        multi = [r for r, rows in by_repo.items() if len(rows) >= 2]
        total_from_multi = sum(len(by_repo[r]) for r in multi)
        if total_from_multi >= n or scanned > 4000:
            break

    # prefer repos with the most sessions (recurrence potential)
    repos_sorted = sorted(by_repo.items(), key=lambda kv: len(kv[1]), reverse=True)
    out = []
    for repo, rows in repos_sorted:
        for row in rows:
            if len(out) >= n:
                break
            out.append({
                "session_id": row.get("instance_id", f"s{len(out)}") + "_" + str(len(out)),
                "repo": repo,
                "trace": _traj_to_text(row.get("trajectory")),
                "success": bool(row.get("target", False)),
            })
        if len(out) >= n:
            break
    return out


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
    ap.add_argument("--n", type=int, default=12)
    ap.add_argument("--k", type=int, default=2)
    ap.add_argument("--out", default="nebius_sample_extractions.json")
    ap.add_argument("--peek", action="store_true", help="print traces, NO model calls (free)")
    args = ap.parse_args()

    print(f"Loading up to {args.n} same-repo trajectories from nebius ...")
    sessions = load_same_repo_sessions(args.n)
    from collections import Counter
    repo_counts = Counter(s["repo"] for s in sessions)
    print(f"  got {len(sessions)} sessions across {len(repo_counts)} repos; "
          f"top repos: {repo_counts.most_common(4)}")
    print(f"  resolved={sum(s['success'] for s in sessions)} "
          f"unresolved={sum(not s['success'] for s in sessions)}")

    if args.peek:
        for s in sessions:
            print(f"\n=== {s['session_id'][:30]}  repo={s['repo']}  "
                  f"success={s['success']}  chars={len(s['trace'])} ===")
            print(s["trace"][:600])
        return

    from openrouter_client import make_completer, DEFAULT_ANSWERER_MODEL
    from session_store import SessionStore
    from gotcha_cluster import cluster_by_judge
    from promotion_engine import promote
    from rule_phrasing import to_negative_constraint_llm
    completer = make_completer(DEFAULT_ANSWERER_MODEL, temperature=0.2, max_tokens=700)

    extractions = {}
    for s in sessions:
        ex = extract_one(s["trace"], completer)
        extractions[s["session_id"]] = ex
        print(f"  {s['session_id'][:30]:30s} repo={s['repo'][:24]:24s} "
              f"gotchas={len(ex.get('gotchas', []))}")

    total = sum(len(e.get("gotchas", [])) for e in extractions.values())
    print(f"\nTotal gotchas from {len(sessions)} real fix-sessions: {total}")

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

    print("\n========== REAL-DATA RESULT (nebius, same-repo) ==========")
    print(f"sessions={len(sessions)} total_gotchas={total} promoted={len(promoted)} (k>={args.k})")
    for a in promoted:
        print(f"  conf={a.meta.confidence} from {len(a.meta.provenance)} sessions {a.meta.provenance}")
        print(f"  rule: {a.content}")
    if not promoted:
        print("  (no promotion - read extractions; same-repo recurrence may still be sparse at this N)")

    out = args.out
    if not os.path.isabs(out):
        out = os.path.join(SCRIPT_DIR, out)
    with open(out, "w") as f:
        json.dump(extractions, f, indent=2)
    print(f"\nRaw extractions saved: {out}  - READ THEM.")
    os.remove(tmp)


if __name__ == "__main__":
    main()
