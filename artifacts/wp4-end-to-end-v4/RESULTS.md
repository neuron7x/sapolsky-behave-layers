# WP4 End-to-End Paid-Halt v4 — Internal Confirmatory Closeout

Verdict: **`SUPPORTED_END_TO_END_INTERNAL`**.

Protocol `b6bc531` preceded implementation `9b9c262`; frozen-threshold repair
`043ff5c` restored the prospectively specified MDE=0.02 before final closeout.
All runs use untouched seeds 300–315, 4096 items, 32 input-blind allocation
replicates, and an identical distribution-derived successor-lookup budget.

| Distribution | Mean adaptive−input-blind solved | 95% bootstrap CI | Worst seed | Adaptive solved | Mean unfinished | Holm p |
|---|---:|---:|---:|---:|---:|---:|
| uniform | 0.1263 | [0.1240, 0.1286] | 0.1182 | 0.6915 | 1769.8 | 0.000107 |
| easy_skew | 0.0739 | [0.0718, 0.0759] | 0.0684 | 0.7510 | 1530.4 | 0.000107 |
| hard_skew | 0.1695 | [0.1660, 0.1733] | 0.1581 | 0.6537 | 2253.8 | 0.000107 |
| bimodal | 0.1003 | [0.0970, 0.1037] | 0.0904 | 0.6231 | 1789.9 | 0.000107 |
| extreme_easy | 0.0422 | [0.0411, 0.0432] | 0.0379 | 0.7701 | 1616.7 | 0.000107 |
| extreme_hard | 0.1627 | [0.1586, 0.1664] | 0.1467 | 0.6363 | 2639.8 | 0.000107 |
| mid_peak | 0.0763 | [0.0748, 0.0778] | 0.0716 | 0.7069 | 2274.8 | 0.000107 |

All four development and all three held-out cells pass the frozen gates.

## Exact claim boundary

The result removes v3.1's free-halt-lookup assumption: a successor lookup is the
atomic cost and the terminal self-loop observation is paid. It establishes a
logical-lookup-budget advantage on this exact synthetic substrate. It does **not**
price controller arithmetic, memory traffic, vectorization inefficiency, wall-clock,
FLOPs, learning a halt policy, halt noise, or real workloads. Therefore it does not
close the scale Pareto, learned-controller, external-validity, independent-replication,
or novelty claims.
