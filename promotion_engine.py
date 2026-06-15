"""
Phase 2 (part 3): the promotion/demotion engine — the "missing diagonal" from
arXiv:2604.15877. Promotes gotchas that RECUR across sessions into compact L3 rules
with lifecycle metadata; demotes rules that fail validation.

Flow:
  1. Pull all gotchas (with source session) from the SessionStore.
  2. Cluster them (embedding or judge backend).
  3. A cluster spanning >= k DISTINCT sessions is a promotion candidate.
  4. Synthesize ONE guardrail-phrased L3 rule from the cluster (RuleShaping).
  5. VALIDATE it (held-out gate) before it graduates — promotion without validation
     is how you promote noise. Optional human confirmation toggle for the 10/10 path.
  6. Attach ArtifactMeta (provenance = the sessions, confidence from evidence count).
  7. Demote a rule that later fails validation back to "demoted" (re-gather evidence).

Honest compromise (per project rule): recurrence is a PROXY for value. The validation
gate + optional human confirmation limit false promotions but don't eliminate them.
The 10/10 is human-in-the-loop ON; the default is gate-only for autonomy. Both shipped.
"""

from __future__ import annotations

import time

from artifact_meta import Artifact, ArtifactMeta, LEVEL_RULE, confidence_from_evidence
from gotcha_cluster import distinct_sessions


def synthesize_rule(cluster: list, reshape_fn) -> str:
    """Turn a cluster of same-lesson gotchas into ONE guardrail rule. We pick the
    most complete phrasing (longest, as a proxy for most context) and reshape it;
    we do NOT concatenate (that produces noise). reshape_fn: gotcha->guardrail."""
    texts = [it["gotcha"] for it in cluster]
    representative = max(texts, key=len)
    return reshape_fn(representative)


def promote(store, *, k_threshold: int, cluster_fn, reshape_fn,
            validate_fn=None, require_human=False, human_confirm_fn=None) -> list:
    """Run one promotion pass. Returns the list of promoted rule Artifacts.

    cluster_fn: items -> list[clusters]
    reshape_fn: gotcha_text -> guardrail rule text
    validate_fn: (rule_text, cluster) -> bool   (held-out gate; None = skip, unsafe)
    require_human + human_confirm_fn: (rule_text, cluster) -> bool   (10/10 path)
    """
    items = store.gotchas_with_source()
    clusters = cluster_fn(items)

    promoted = []
    for cluster in clusters:
        n_sessions = distinct_sessions(cluster)
        if n_sessions < k_threshold:
            continue   # not enough cross-session evidence

        rule_text = synthesize_rule(cluster, reshape_fn)

        # validation gate: a promoted rule must survive a held-out check
        validated = True
        if validate_fn is not None:
            try:
                validated = bool(validate_fn(rule_text, cluster))
            except Exception:
                validated = False
        if not validated:
            continue   # do not promote unvalidated rules (avoid compact noise)

        # optional human-in-the-loop confirmation (the 10/10 path)
        if require_human:
            if human_confirm_fn is None or not human_confirm_fn(rule_text, cluster):
                continue

        meta = ArtifactMeta(
            level=LEVEL_RULE,
            provenance=sorted({it["session_id"] for it in cluster}),
            confidence=confidence_from_evidence(n_sessions, k_threshold),
            status="active",
            notes=f"promoted from {n_sessions} sessions",
        )
        if validate_fn is not None:
            meta.mark_validated()
        promoted.append(Artifact(content=rule_text, meta=meta))

    return promoted


def demote(rule: Artifact, *, validate_fn, cluster=None, reason: str = "") -> bool:
    """Re-validate an existing rule; if it now fails, demote it. Returns True if the
    rule was demoted. Demotion reverts to evidence-gathering (status='demoted')."""
    try:
        ok = bool(validate_fn(rule.content, cluster or []))
    except Exception:
        ok = False
    if ok:
        rule.meta.mark_validated()
        return False
    rule.meta.status = "demoted"
    rule.meta.notes = (rule.meta.notes + f" | demoted: {reason or 'failed re-validation'}").strip(" |")
    return True
