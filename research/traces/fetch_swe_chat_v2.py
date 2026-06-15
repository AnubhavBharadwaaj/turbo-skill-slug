"""
Download a handful of REAL DEBUGGING sessions from SWE-chat (not tiny review stubs).

Two fixes over v1:
  1. Target MEDIUM files (default 300KB-1.5MB): real debugging arcs have many turns;
     the tiny <130KB files were mostly Codex *review* sessions (agent grading a PR),
     which have no try/fail/recover gotchas to extract.
  2. After download, peek at each file's session_meta and SKIP pure-review sessions
     (originator/subagent == 'review', or reviewer rubric in base_instructions),
     keeping only sessions likely to contain debugging struggle.

Run locally:
    export HF_TOKEN=hf_...
    python fetch_swe_chat_v2.py --n 8 --min-mb 0.3 --max-mb 1.5 --out ./swe_chat_traces
"""

from __future__ import annotations

import argparse
import json
import os


def _looks_like_review(path: str) -> bool:
    """Read the session_meta (near the top) and decide if this is a review/grading
    session rather than a debugging session. Conservative: skip only on clear signal."""
    try:
        with open(path) as f:
            for _ in range(5):
                line = f.readline()
                if not line:
                    break
                try:
                    obj = json.loads(line)
                except Exception:
                    continue
                if obj.get("type") == "session_meta":
                    p = obj.get("payload", {}) or {}
                    originator = str(p.get("originator", "")).lower()
                    sub = str(((p.get("source") or {}).get("subagent") or "")).lower()
                    instr = str((p.get("base_instructions") or {}).get("text", "")).lower()
                    if "review" in sub or "review" in originator:
                        return True
                    if "acting as a reviewer" in instr or "whether something is a bug" in instr:
                        return True
                    return False
    except Exception:
        pass
    return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=8)
    ap.add_argument("--min-mb", type=float, default=0.3, help="skip files smaller than this")
    ap.add_argument("--max-mb", type=float, default=1.5, help="skip files larger than this")
    ap.add_argument("--out", default="./swe_chat_traces")
    ap.add_argument("--scan", type=int, default=60, help="how many candidate files to size-check")
    args = ap.parse_args()

    from huggingface_hub import HfApi, hf_hub_download
    token = os.environ.get("HF_TOKEN")
    api = HfApi()
    repo_id = "SALT-NLP/SWE-chat"

    print(f"Listing transcript files in {repo_id} ...")
    files = api.list_repo_files(repo_id=repo_id, repo_type="dataset", token=token)
    transcripts = [f for f in files if f.startswith("transcripts/") and f.endswith(".jsonl")]
    print(f"  {len(transcripts)} transcripts total; sizing a sample in "
          f"[{args.min_mb}, {args.max_mb}] MB ...")

    in_window = []
    BATCH = 200
    for i in range(0, min(len(transcripts), args.scan * 6), BATCH):
        infos = api.get_paths_info(repo_id=repo_id, repo_type="dataset",
                                   paths=transcripts[i:i+BATCH], token=token)
        for info in infos:
            mb = (getattr(info, "size", None) or 0) / 1e6
            if args.min_mb <= mb <= args.max_mb:
                in_window.append((info.path, mb))
        if len(in_window) >= args.n * 4:
            break
    in_window.sort(key=lambda x: x[1], reverse=True)   # prefer larger (more turns) first
    print(f"  {len(in_window)} files in size window; downloading + screening for debugging sessions")

    out_is_manifest = args.out.endswith((".jsonl", ".txt"))
    local_dir = (
        os.path.splitext(args.out)[0] + "_files"
        if out_is_manifest else args.out
    )
    os.makedirs(local_dir, exist_ok=True)
    kept = []
    for path, mb in in_window:
        if len(kept) >= args.n:
            break
        lp = hf_hub_download(repo_id=repo_id, repo_type="dataset", filename=path,
                             local_dir=local_dir, token=token)
        if _looks_like_review(lp):
            print(f"  skip (review session): {os.path.basename(path)}")
            continue
        kept.append(lp)
        print(f"  keep ({mb:.2f} MB): {os.path.basename(path)}")

    manifest = args.out if out_is_manifest else os.path.join(args.out, "_manifest.txt")
    with open(manifest, "w") as f:
        for lp in kept:
            f.write(lp + "\n")
    print(f"\nKept {len(kept)} debugging sessions -> {manifest}")
    print("Next: python run_swe_chat_phases.py --manifest", manifest, "--k 2")


if __name__ == "__main__":
    main()
