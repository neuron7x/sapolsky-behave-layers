# R3-C — End-to-End Routing Without Oracle Leakage — RESULTS

VERDICT: **`ROUTING_END_TO_END_NOT_SUPPORTED`** (8 seeds). The decisive P0 test.

Removing the three leaks (label-derived capacity, value-distillation target,
ground-truth in the controller signal) and training the controller ONLY on task
loss under a fixed pre-chosen budget: routing **collapses**.

| metric | mean (8 seeds) | reading |
|---|---:|---|
| learned routed loss | 0.911 | WORSE than random |
| random routed loss | 0.480 | baseline |
| route balanced accuracy | 0.045 | ~0 = inverse routing |
| route AUROC (need vs HARD) | 0.011 | ~0 = routes EASY->semantic |

learned worse than random on ALL seeds: True.

## What this establishes
1. The v2 `ROUTING_CAUSALITY_SUPPORTED` was **load-bearingly dependent on
   counterfactual value distillation** — remove it and end-to-end routing does
   not reproduce. The narrowed claim (`../wp2-routing-v2/claim_boundary.json`)
   STANDS; it is a real dependency, not a caveat.
2. The failure is credit-assignment, not benchmark: the oracle gap is 99.8%
   (identifiable), yet straight-through top-K on task loss collapses to the
   inverse — the same pattern as routing v1 and plasticity Stage B (mechanism
   exists; the unsupervised optimizer does not find it).
3. Metric lesson: symmetric NMI stays 0.6-0.95 while balanced accuracy ~0 —
   association is not direction. Only the corrected balanced-accuracy + AUROC
   expose the inversion. Vindicates the P0.7 metric fix.

## Honest next step
Autonomous end-to-end adaptive routing here needs a better credit-assignment
signal than straight-through top-K (a learned value/advantage estimator that is
NOT the ground-truth path benefit, or an RL allocator). Until then the routing
claim remains narrowed to the value-distillation regime.
