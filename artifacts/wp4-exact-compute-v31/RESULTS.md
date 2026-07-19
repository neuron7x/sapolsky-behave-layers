# WP4 Exact-Compute v3.1 — Internal Confirmatory Closeout

Verdict: **`SUPPORTED_NARROWED_INTERNAL`**.

Protocol amendment `760ebcd` preceded implementation `2ef3da8` and untouched
data seeds 200–215. Invalid v3 seeds 100–115 were excluded. All primary cells
used a distribution-derived frozen budget and exact integer operator-hop equality.

| Distribution | Mean adaptive−input-blind solved | 95% bootstrap CI | Worst seed |
|---|---:|---:|---:|
| uniform | 0.4269 | [0.4207, 0.4321] | 0.3978 |
| easy_skew | 0.3084 | [0.3026, 0.3135] | 0.2818 |
| hard_skew | 0.5077 | [0.4987, 0.5147] | 0.4568 |
| bimodal | 0.4625 | [0.4515, 0.4711] | 0.4012 |
| extreme_easy | 0.2643 | [0.2617, 0.2668] | 0.2545 |
| extreme_hard | 0.5046 | [0.4931, 0.5143] | 0.4491 |
| mid_peak | 0.3593 | [0.3554, 0.3630] | 0.3402 |

All four development distributions and all three held-out shifts pass the
frozen MDE, exact randomization and Holm gates.

## Hard claim boundary

This result compares **operator-hop allocation conditional on a free exact halt
oracle**. It is not an end-to-end compute result. A post-hoc descriptive audit
finds 1.12–1.39 halt evaluations per billed operator hop; if a halt evaluation
costs one operator hop, adaptive execution costs roughly 2.12–2.39 times the
operator-only ledger. No Pareto, latency, energy, learned-controller, novelty,
real-workload, external-preregistration or independent-replication claim follows.

The supported statement is only: on this synthetic substrate, under a frozen
operator-hop budget and free exact halt information, halt-conditioned allocation
solves more items than an input-blind allocation with the same operator hops.
