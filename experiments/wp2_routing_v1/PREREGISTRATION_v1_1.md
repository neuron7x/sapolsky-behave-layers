# WP-2 Routing v1.1 — PREREGISTRATION (binding budget, heterogeneous task)

Registered 2026-07-16 BEFORE the run, committed before analysis. Follows the
Act; this is the decisive experiment WP-2 v1 RESULTS explicitly called for
("re-run at a binding budget on a task with input-dependent required depth").

## Why v1.1
v1 returned ROUTER_COLLAPSE and NOT_SUPPORTED, but with a documented limit:
K=4 was near-sufficient (static 4-of-8 matched dense), and all sequences
needed the same mechanism → no reason for adaptivity to help. v1.1 removes both
confounds:
1. **Binding budget K=2 of 8** — a static pair must compromise.
2. **Heterogeneous task** — each sequence is RECALL (needs induction, deep) or
   COPY (needs a shallow retrieval head). A controller that routes *by type*
   can serve both; a static selection cannot. Adaptivity now CAN win.

This makes the test fair to the hypothesis: if learned routing still fails to
beat static here, the negative is strong (adaptivity provably could have
helped). If it wins, that is the first genuine positive signal.

## Hypotheses
- **H1'**: at K=2, `answer_ce(learned) < answer_ce(random)` AND
  `< answer_ce(frozen)` AND `< answer_ce(fixed_depth)`, paired across seeds.
- **H2'** (adaptivity, the mechanistic claim): the learned controller routes
  COPY and RECALL sequences to DIFFERENT block sets — measured by
  `routing_divergence_copy_vs_recall` (L1 distance of per-type utilization)
  significantly > 0, while static/frozen have divergence ≈ 0.

## Failure conditions (unchanged from Act C3)
learned ≈ any static control; router collapse (per-type divergence ≈ 0 →
learned ignored the type); gain vanishes after parity; unstable across seeds.

## Fixed design
- Task `task_mixed.py`: p_recall=0.5, n_pairs=6, seq_len=64, flags at pos 0.
- Model: L=8, d_model=128, n_head=4, d_ff=512, **K=2**.
- Controller: same straight-through top-K (ADR-0002), per-sequence pooled input.
- Controls: dense (ceiling), random, frozen, learned, fixed_depth. Same
  init/data/optimizer/tokens per seed.
- Training: 2500 steps, AdamW lr=1e-3, batch=64, warmup=100, checkpoint =
  min val answer_ce. Val = 2000 fixed sequences (Generator 999_999).
- **Seeds: 5 {0,1,2,3,4}** — claim tier (Act G3), not just pilot.
- Compute parity: K-configs share K=2 active blocks; controller FLOPs counted.
- Energy: EXCLUDED (INSTRUMENT_INVALID).

## Statistics & verdict
Unit = seed. Paired bootstrap 95% CI of learned − each control on answer_ce
(lower better). Verdict ∈ {ROUTING_SUPPORTED, ROUTING_NOT_SUPPORTED,
ROUTER_COLLAPSE, COMPUTE_MISMATCH, MEASUREMENT_INVALID}. Additionally report
per-type accuracy (recall/copy) and per-type routing divergence — the direct
adaptivity evidence. A NULL is a valid negative completion (Act §17).
No threshold is changed after seeing results.
