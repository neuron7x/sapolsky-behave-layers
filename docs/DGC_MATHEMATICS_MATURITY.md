# DGC Mathematics Maturity — Weighted Evidence Rubric

Date: 2026-08-22

This score measures **coverage of mathematical obligations**, not probability that DGC is commercially successful and not a claim of theorem novelty.

\[
M=\sum_j w_j s_j,\qquad \sum_j w_j=100,\qquad s_j\in[0,1].
\]

A dimension receives 100% only when definitions, assumptions, failure conditions, executable checks and relevant empirical/calibration obligations are closed.

| Dimension | Weight | Current score | Weighted points | Why not 100% |
|---|---:|---:|---:|---|
| Decision theory / VOI / VOC semantics | 12 | 94% | 11.28 | finite-horizon oracle + PI gap bound exist; scalable multi-step control remains approximate |
| Robustness / ambiguity / misspecification | 14 | 86% | 12.04 | ambiguity geometry and budgets are externally declared, not learned/validated |
| Sequential / adaptive validity | 14 | 80% | 11.20 | predictable-IPW case closed; arbitrary adaptive search remains open |
| Calibration / estimated VOC risk control | 10 | 82% | 8.20 | conformal primitives exist; no client-distribution calibration evidence |
| Causal countermodels / identifiability | 12 | 78% | 9.36 | structural authority exists; broad identifiability remains conditional |
| Decision stability / removable-compute theory | 10 | 90% | 9.00 | certified suffix theorem is narrow; general DAG compute-removability not solved |
| Pareto / economic statistical inference | 10 | 86% | 8.60 | paired simultaneous gate exists; strong external same-workload benchmark unresolved |
| Executable falsification / proof obligations | 8 | 94% | 7.52 | 9 math attacks exist; no proof assistant / independent formal review |
| Nonstationarity / generalization theory | 6 | 67% | 4.02 | bounded-drift independent case closed; unknown/dependent/adversarial drift remains open |
| External theorem review / novelty boundary | 4 | 38% | 1.52 | foundational metareasoning prior art mapped; no independent theorem-by-theorem review |
| **TOTAL** | **100** |  | **82.74%** | |

## Canonical score

\[
\boxed{M_{math}=82.7\%}
\]

Status: `MATHEMATICALLY_HARDENED_RESEARCH_SYSTEM`, not `FORMALLY_COMPLETE`.

The previous ~95% estimate is rejected as insufficiently grounded. The earlier state was directionally closer to ~73% because it lacked explicit ambiguity robustness, adaptive importance-weighted inference, credal semantics, conformal risk control, simultaneous Pareto authority, bounded-drift treatment and a nonmyopic error boundary.

## Promotion to >=90%

Requires material closure of all of:

1. general adaptive-selection validity or a formally justified restricted production sampling policy;
2. unknown/change-point/dependent drift handling beyond externally bounded independent drift;
3. client-distribution estimated-VOC calibration and risk control;
4. continuous/high-dimensional ambiguity with validated metric/geometry;
5. useful scalable multi-step VOC approximation-error bounds beyond the loose perfect-information ceiling;
6. independent theorem review / systematic prior-art equivalence audit;
7. no surviving mathematical mutation/falsification attacks.

Without those, reporting `>=90% mathematics complete` is prohibited.
