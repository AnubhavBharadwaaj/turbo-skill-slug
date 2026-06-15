"""
Phase 2 (part 2): cluster gotchas that express the SAME underlying lesson across
sessions, so recurring ones can be promoted.

Two backends:
  - cluster_by_embedding(gotchas, embed_fn, threshold): cosine over embeddings.
  - cluster_by_judge(gotchas, judge_fn): an LLM decides if two gotchas are "the
    same underlying gotcha". Used when no embedder is available.

Both return clusters: lists of {gotcha, session_id} groups. A cluster spanning >= k
DISTINCT sessions is a promotion candidate (the engine, not this module, decides).

We keep clustering conservative (high threshold / strict judge) because a loose
clusterer promotes noise — the failure mode the spectrum paper warns about
("compact noise"). Precision over recall here.
"""

from __future__ import annotations

import math


def _cosine(a, b) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a)) or 1.0
    nb = math.sqrt(sum(y * y for y in b)) or 1.0
    return dot / (na * nb)


def cluster_by_embedding(items: list, embed_fn, threshold: float = 0.82) -> list:
    """items: [{gotcha, session_id}]. embed_fn: list[str]->list[vec]. Greedy
    agglomeration: each item joins the first cluster whose centroid it exceeds
    threshold with, else starts a new cluster."""
    if not items:
        return []
    vecs = embed_fn([it["gotcha"] for it in items])
    clusters = []   # each: {"items":[...], "centroid":[...]}
    for it, v in zip(items, vecs):
        placed = False
        for c in clusters:
            if _cosine(v, c["centroid"]) >= threshold:
                c["items"].append(it)
                # update centroid (running mean)
                n = len(c["items"])
                c["centroid"] = [(cc * (n - 1) + vv) / n for cc, vv in zip(c["centroid"], v)]
                placed = True
                break
        if not placed:
            clusters.append({"items": [it], "centroid": list(v)})
    return [c["items"] for c in clusters]


def cluster_by_judge(items: list, judge_fn) -> list:
    """judge_fn(a,b)->bool: are these the same underlying gotcha? Greedy: compare
    each item to one representative per existing cluster."""
    clusters = []   # each: list of items; clusters[i][0] is the representative
    for it in items:
        placed = False
        for c in clusters:
            try:
                if judge_fn(c[0]["gotcha"], it["gotcha"]):
                    c.append(it)
                    placed = True
                    break
            except Exception:
                continue
        if not placed:
            clusters.append([it])
    return clusters


def distinct_sessions(cluster: list) -> int:
    return len({it["session_id"] for it in cluster})
