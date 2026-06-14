"""
Novel-trap eval cases: traps the model CANNOT know from training data, because the
rules are invented (fictional APIs / systems with arbitrary, non-derivable behavior).

The whole point: a frontier model can reason its way out of a KNOWN trap (Kahan,
N+1, races) because that knowledge is in its weights. It CANNOT reason its way out
of an ARBITRARY rule it has never seen. If skill files have any value for frontier
models, it must show up HERE — where the only way to know the trap is to be told.

Design contract:
  - The system is fictional and the failing behavior is ARBITRARY (not derivable).
  - The OBVIOUS approach (what any sensible engineer/model would write) is wrong
    in this fictional system for a reason only the skill reveals.
  - The skill's gotcha states the rule WITHOUT just handing over the final code.
  - trap_desc / correct_desc let the blind judge classify the primary recommendation.
  - leak_terms: the skill must not contain the literal task answer.

These mimic the REAL value case: a proprietary codebase with undocumented behavior.
"""
from distractor_eval import DistractorCase

CASES = [
    # 1. A fictional database driver whose commit() is a no-op without a prior fence.
    DistractorCase(
        name="zthread_fence_before_commit",
        session_extraction={
            "themes": ["zthrumdb driver", "transactions"],
            "approaches_tried": [
                {"approach": "call conn.begin(); ...writes...; conn.commit() as normal",
                 "why_it_failed": "in zthrumdb, commit() silently no-ops unless conn.fence() is called first; writes were lost with no error"},
            ],
            "dead_ends": [{"position": 0.4, "what_happened":
                "the standard begin/commit pattern returned success but the rows were never persisted; zthrumdb requires a fence() barrier before commit() or commit is ignored"}],
            "breakthroughs": [{"position": 0.85, "what_worked":
                "call conn.fence() immediately before conn.commit(); without the fence, zthrumdb buffers and silently drops the transaction"}],
            "gotchas": [
                "In the zthrumdb driver, conn.commit() silently no-ops (returns success, persists nothing) unless conn.fence() is called immediately before it. Always fence() right before commit() or the transaction is dropped with no error.",
            ],
            "sentiment_arc": {"start": "confident", "end": "baffled"},
        },
        task_prompt=("Using the zthrumdb Python driver, write a function that opens a connection, "
                     "inserts three rows in a transaction, and durably commits them. Show the code."),
        trap_signature=[], correct_signature=[],
        leak_terms=["write a function that opens a connection, inserts three rows"],
        trap_desc="Standard begin/insert/commit without calling conn.fence() before conn.commit().",
        correct_desc="Calls conn.fence() immediately before conn.commit() so zthrumdb actually persists the transaction.",
    ),

    # 2. A fictional rate limiter where the LIMIT param is per-MINUTE but resets only
    #    when you read .remaining (reading has a side effect). Arbitrary, non-derivable.
    DistractorCase(
        name="qbucket_read_resets",
        session_extraction={
            "themes": ["qbucket limiter", "rate limiting"],
            "approaches_tried": [
                {"approach": "check limiter.remaining > 0 before each call, sleep when it hits 0",
                 "why_it_failed": "reading .remaining in qbucket RESETS the window as a side effect, so polling it in a loop made the limit never actually apply"},
            ],
            "dead_ends": [{"position": 0.45, "what_happened":
                "polling limiter.remaining to decide whether to wait accidentally kept resetting the bucket, so the rate limit was never enforced and we got banned"}],
            "breakthroughs": [{"position": 0.85, "what_worked":
                "read limiter.remaining exactly once per window and cache it locally; never poll it in a loop, because each read resets the qbucket window"}],
            "gotchas": [
                "In qbucket, reading limiter.remaining has a SIDE EFFECT: it resets the rate-limit window. Never poll .remaining in a loop to decide whether to wait; read it at most once per window and track remaining count locally, or you disable your own rate limiting.",
            ],
            "sentiment_arc": {"start": "confident", "end": "alarmed"},
        },
        task_prompt=("Using the qbucket rate limiter, write a loop that makes 1000 API calls while "
                     "respecting the limiter so you never exceed the allowed rate. Show the code."),
        trap_signature=[], correct_signature=[],
        leak_terms=["write a loop that makes 1000 API calls"],
        trap_desc="Polling limiter.remaining inside the loop to decide whether to wait.",
        correct_desc="Reads limiter.remaining at most once per window and tracks the count locally, never polling it in the loop, because reading resets the qbucket window.",
    ),

    # 3. A fictional serializer where lists must be tagged or they deserialize REVERSED.
    DistractorCase(
        name="flazon_list_tag_reversal",
        session_extraction={
            "themes": ["flazon serializer", "serialization"],
            "approaches_tried": [
                {"approach": "flazon.dump(my_list) then flazon.load(...) round-trip as usual",
                 "why_it_failed": "flazon deserializes untagged lists in REVERSE order; round-tripping silently reversed the data unless the list was wrapped with flazon.ordered()"},
            ],
            "dead_ends": [{"position": 0.5, "what_happened":
                "round-tripping a list through flazon silently reversed its order; flazon requires flazon.ordered(list) on dump or it restores elements last-to-first"}],
            "breakthroughs": [{"position": 0.85, "what_worked":
                "wrap lists in flazon.ordered() before dump; untagged lists come back reversed because flazon stores them as a LIFO stack internally"}],
            "gotchas": [
                "flazon serializes untagged lists as a LIFO stack, so flazon.load reverses their order on the way back. Always wrap lists with flazon.ordered() before flazon.dump, or your data round-trips reversed with no error.",
            ],
            "sentiment_arc": {"start": "confident", "end": "confused"},
        },
        task_prompt=("Using the flazon serializer, write code that serializes a list of 5 user records "
                     "to bytes and deserializes them back, preserving their original order. Show the code."),
        trap_signature=[], correct_signature=[],
        leak_terms=["serializes a list of 5 user records"],
        trap_desc="Plain flazon.dump(list) / flazon.load without wrapping the list in flazon.ordered().",
        correct_desc="Wraps the list in flazon.ordered() before flazon.dump so it round-trips in the original order instead of reversed.",
    ),
]
