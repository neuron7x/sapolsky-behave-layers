# WP19 — Robustness of the WP18 Negative (PREREGISTRATION)

**Act:** CWC-ASCEND-2026-01. Committed separately, before any result exists.
**Class ceiling:** this WP can only **narrow or confirm an existing negative**. It cannot create a
positive claim, and it is explicitly *not* a search for a difficulty signal that works (WP18's
prereg forbids that, and this WP does not touch the difficulty signal at all).

## Why this exists
WP18's kill rule stopped architecture work on the strength of a **negative**. A negative that halts
a programme must be attacked as hard as a positive. WP18 has a concrete, unaddressed confound:

> Every WP18 model was a **weight-tied recurrent block** trained with K cycled uniformly over
> {1,2,3}. The finding "modal best K = 2 in every difficulty bucket" may therefore be a property of
> **that training protocol and that compute axis** — a shared block trained to be adequate at all K
> has an obvious interior optimum — rather than a property of real data.

If the absence of a context × resource interaction is an artifact of the mechanism, WP18's boundary
is mechanism-specific and must be narrowed. Establishing that is the only honest way to let the
kill rule stand.

## Question
Does a **structurally different compute axis** on the **same real workloads and the same held-out
eval shards** also show no context × resource interaction?

- **Axis A (WP18, already measured):** weight-tied block applied K ∈ {1,2,3} times, one model
  trained on all K.
- **Axis B (new):** **untied depth** — three *separate* models with L ∈ {1,2,3} independent blocks,
  each trained on its own, no weight sharing, no multi-K training. This is the conventional
  "depth = compute" axis and shares none of axis A's degeneracies.

Everything else is held fixed: same corpora, same hash-based splits, same 5 held-out eval shards,
same bigram-surprisal difficulty terciles, same certificate, same δ=0.05, same measured
`c_route = 0.0006`.

## Frozen decision rule
- `NEGATIVE_ROBUST_ACROSS_COMPUTE_AXES` iff on axis B **both** workloads again have
  `G_lo ≤ c_route` **and** the modal best depth is the same in every difficulty bucket.
  → WP18's boundary is a property of the data, not of the weight-tied mechanism; the kill rule
  stands as written.
- `NEGATIVE_IS_MECHANISM_SPECIFIC` iff axis B yields `G_lo > c_route` on either workload, **or** the
  modal best depth differs across difficulty buckets.
  → WP18's `CWC-RD3` must be **NARROWED** to the weight-tied axis, and the kill rule's scope
  narrowed with it. This outcome is *against* my own prior conclusion and will be registered as
  such, not re-run away.
- `WP19_VOID` if the mandatory synthetic positive control fails to certify.

## Procedure
2 workloads × 3 depths (L=1,2,3) × 3 seeds = 18 independently trained models, each evaluated on the
same 5 held-out eval shards → per-bucket loss at each depth. Identical training budget per model
(same steps/batch/LR as WP18) so depth is the only compute variable. Deterministic given seeds.

## Kill rules (falsifiers)
- VOID if the synthetic positive control does not certify in the same run.
- The result that would *hurt* me (mechanism-specific) is fully specified above and will be
  registered if observed. No post-hoc redefinition of "interaction".

## Prohibited extrapolations
- No architecture claim, no L7 statement, no "adaptive compute never helps real LMs".
- A robust negative here does **not** license claiming the boundary holds at large pretrained scale;
  it only removes the weight-tying confound at pilot scale.
