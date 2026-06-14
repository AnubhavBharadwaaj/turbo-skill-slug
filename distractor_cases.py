"""
Distractor-trap eval cases: tasks where the OBVIOUS approach is WRONG in a
non-obvious way, and the skill's gotcha warns about exactly that trap.

Design contract for each case (to keep the eval honest):
  - task_prompt: a task whose naive solution is tempting but subtly wrong.
  - the SESSION the skill is built from contains the TRAP as a gotcha (negative
    knowledge), phrased so it warns WITHOUT just stating this task's final answer.
  - trap_signature: strings that appear if the model FELL for the distractor.
  - correct_signature: strings that appear if the model AVOIDED the trap.
  - leak_terms: if the skill literally contains the task's answer, it's excluded.

These are deliberately at the EDGE of frontier ability: each is a known footgun
where even strong models often produce confident wrong answers on the first pass.
"""
from distractor_eval import DistractorCase

CASES = [
    # 1. Floating-point: summing many small floats naively loses precision.
    DistractorCase(
        name="float_sum_kahan_trap",
        session_extraction={
            "themes": ["numerical precision", "floating point"],
            "approaches_tried": [
                {"approach": "sum the values in a simple loop", "why_it_failed":
                 "naive accumulation lost low-order bits; the running total swamped small addends and the result drifted"},
            ],
            "dead_ends": [{"position": 0.4, "what_happened":
                "a plain left-to-right sum gave a visibly wrong total on 1e7 values near machine epsilon"}],
            "breakthroughs": [{"position": 0.85, "what_worked":
                "used compensated (Kahan) summation to carry the lost low-order error term"}],
            "gotchas": [
                "Summing many floats with a naive running total silently loses precision because each addition rounds off the small addend against a large accumulator; use compensated summation or sort-by-magnitude.",
            ],
            "sentiment_arc": {"start": "confident", "end": "humbled"},
        },
        task_prompt=("Write a function that returns the sum of a list of 10 million float64 "
                     "values that range over many orders of magnitude (some ~1e8, many ~1e-8). "
                     "Accuracy to the last few bits matters. Give the approach and why."),
        trap_signature=["simple loop", "just sum", "sum(", "total += ", "naive"],
        correct_signature=["kahan", "compensated", "neumaier", "sort", "pairwise", "math.fsum", "fsum"],
        leak_terms=["10 million float64 values that range over many orders"],
        trap_desc="Summing in a plain left-to-right loop (total += x or sum()), which loses precision.",
        correct_desc="Compensated summation (Kahan/Neumaier), pairwise summation, sorting by magnitude, or math.fsum.",
    ),

    # 2. Concurrency: check-then-act race on a shared dict / cache.
    DistractorCase(
        name="check_then_act_race",
        session_extraction={
            "themes": ["concurrency", "race conditions"],
            "approaches_tried": [
                {"approach": "if key not in cache: cache[key]=compute()", "why_it_failed":
                 "two threads passed the 'not in' check simultaneously and both computed, double-work and an inconsistent cache"},
            ],
            "dead_ends": [{"position": 0.5, "what_happened":
                "the check-then-act pattern looked atomic but wasn't; under load the value was computed twice"}],
            "breakthroughs": [{"position": 0.85, "what_worked":
                "guarded the check-and-set with a lock, or used an atomic get-or-compute primitive"}],
            "gotchas": [
                "A 'if key not in cache: cache[key] = compute()' is a check-then-act race: two threads can both pass the check before either writes; make the check and write atomic with a lock or a get-or-compute primitive.",
            ],
            "sentiment_arc": {"start": "confident", "end": "wary"},
        },
        task_prompt=("In a multithreaded service, implement a memoizing cache so an expensive "
                     "compute(key) runs at most once per key even under concurrent access. "
                     "Show the implementation and explain why it is correct."),
        trap_signature=["if key not in", "if key in cache", "not in self", "not in cache"],
        correct_signature=["lock", "with self._lock", "threading.lock", "atomic", "setdefault", "double-checked", "futures"],
        leak_terms=["memoizing cache so an expensive compute"],
        trap_desc="A check-then-act 'if key not in cache: cache[key]=compute()' with no synchronization.",
        correct_desc="Synchronize the check-and-set with a lock (double-checked), or use an atomic get-or-compute / futures.",
    ),

    # 3. SQL / N+1: the obvious ORM loop is correct but pathologically slow.
    DistractorCase(
        name="n_plus_one_query",
        session_extraction={
            "themes": ["database performance", "ORM"],
            "approaches_tried": [
                {"approach": "loop over parents, query children per parent", "why_it_failed":
                 "issued one query per parent (N+1 queries); correct results but it fell over at scale"},
            ],
            "dead_ends": [{"position": 0.45, "what_happened":
                "the per-row query loop worked in tests with 5 rows and timed out in prod with 50k"}],
            "breakthroughs": [{"position": 0.85, "what_worked":
                "eager-loaded children in one query (join / IN clause / select_related) instead of per-parent queries"}],
            "gotchas": [
                "Looping over parent rows and querying each parent's children separately is the N+1 query trap: it is correct but issues one query per row and dies at scale; fetch related rows in a single query (join or IN) instead.",
            ],
            "sentiment_arc": {"start": "confident", "end": "chastened"},
        },
        task_prompt=("Given 50,000 authors, return each author with their list of books from a "
                     "relational DB via an ORM. Write the query/code and explain the performance "
                     "characteristics."),
        trap_signature=["for author in", "author.books", "query per", "loop", ".filter(author"],
        correct_signature=["join", "select_related", "prefetch", "eager", "IN (", "single query", "one query", "joinedload"],
        leak_terms=["50,000 authors, return each author with their list of books"],
        trap_desc="Looping over parents and issuing one child query per parent (N+1 queries).",
        correct_desc="Fetch related rows in a single query: join, IN clause, select_related/prefetch/joinedload.",
    ),
]
