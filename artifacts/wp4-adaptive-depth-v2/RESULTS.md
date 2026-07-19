# WP4 Adaptive Depth v2 — Corrective Results

Verdict: **`SYNTHETIC_HALT_IDENTITY_VERIFIED`**.

The exact halt-oracle implementation verifies
`adaptive_solved - static_solved = P_sample(m > K)` to numerical precision over
8 deterministic seeds and 4 distributions. Two-sided bootstrap intervals for
adaptive-minus-random are non-degenerate after replacing the faulty LCG.

The exact-compute gate **fails** in 3 of 4 distributions:

| Distribution | Relative hop mismatch | <=1% |
|---|---:|---:|
| uniform | 0.09% | PASS |
| easy_skew | 3.34% | FAIL |
| hard_skew | 1.72% | FAIL |
| bimodal | 2.51% | FAIL |

Therefore this result is an executable identity/positive control only. It is
not evidence of an equal-compute Pareto advantage.
