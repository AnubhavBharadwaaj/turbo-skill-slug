"""Sample eval cases: each session paired with a DISTINCT held-out task in the
same class. These are illustrative; swap in your real sessions when running."""
from skill_uplift_eval import EvalCase

CASES = [
    EvalCase(
        name="tree_dp_to_new_tree_problem",
        session_extraction={
            "themes": ["tree dynamic programming", "processing order"],
            "approaches_tried": [
                {"approach": "top-down recursion", "why_it_failed": "recomputed each subtree per ancestor, O(n^2)"},
                {"approach": "process leaves first", "why_it_failed": "a parent's value needs children finalized first"},
            ],
            "dead_ends": [{"position": 0.3, "what_happened": "stack overflow on deep trees"}],
            "breakthroughs": [{"position": 0.85, "what_worked": "compute bottom-up, deepest nodes first, memoizing subtree results"}],
            "gotchas": [
                "Top-down recursion recomputes subtrees for every ancestor, making it O(n^2); compute bottom-up once instead.",
                "Processing leaves first feels natural but a parent depends on its children being finalized; process deepest-first.",
            ],
            "sentiment_arc": {"start": "frustrated", "end": "resolved"},
        },
        # DISTINCT task: a different tree-DP problem, same class
        task_prompt=("Given a tree where each node has a value, compute for every node "
                     "the maximum sum of any path from that node down to a leaf, efficiently. "
                     "Describe the algorithm and its time complexity. Be concise."),
        answer_key_terms=["bottom-up", "post-order", "children", "O(n)"],
        # if the skill literally contained THIS task's answer it'd be leakage
        leak_terms=["maximum sum of any path from that node down to a leaf"],
    ),
    EvalCase(
        name="markov_to_new_absorbing_chain",
        session_extraction={
            "themes": ["markov chains", "absorbing states"],
            "approaches_tried": [
                {"approach": "simulate many runs", "why_it_failed": "variance too high to converge on the exact value"},
                {"approach": "solve the full linear system", "why_it_failed": "singular at the absorbing state's row"},
            ],
            "dead_ends": [{"position": 0.4, "what_happened": "matrix inversion failed, singular"}],
            "breakthroughs": [{"position": 0.85, "what_worked": "drop the absorbing row, solve only the transient states' first-step equations"}],
            "gotchas": [
                "The absorbing-state row makes the system singular; exclude it and solve only transient states.",
                "Expected hitting time is not absorption probability; do not conflate them.",
            ],
            "sentiment_arc": {"start": "frustrated", "end": "resolved"},
        },
        task_prompt=("In a random walk on states 0..4 where 0 and 4 are absorbing, find the "
                     "probability of being absorbed at 4 starting from state 2. Describe the "
                     "method, not just the number. Be concise."),
        answer_key_terms=["transient", "first-step", "linear", "exclude"],
        leak_terms=["absorbed at 4 starting from state 2"],
    ),
]
