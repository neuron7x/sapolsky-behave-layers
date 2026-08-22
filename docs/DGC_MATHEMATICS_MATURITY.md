# DGC Mathematics Maturity — Weighted Evidence Rubric

Date: 2026-08-22

This score measures **coverage of mathematical obligations**, not probability that DGC is commercially successful and not a claim of theorem novelty.

Formula:

\[
M=\sum_j w_j s_j,
\qquad \sum_j w_j=100,
\qquad s_j\in[0,1].
\]

A dimension receives 100% only when its definitions, assumptions, failure conditions, executable checks and relevant empirical/calibration obligations are all closed. A theorem proved only under synthetic/exchangeable/finite assumptions cannot score the corresponding real-world dimension at 100%.

| Dimension | Weight | Current score | Weighted points | Why not 100% |
|---|---:|---:|---:|---|
| Decision theory / VOI / VOC semantics | 12 | 92% | 11.04 | multi-step metareasoning remains approximate |
| Robustness / ambiguity / misspecification | 14 | 86% | 12.04 | ambiguity geometry and budgets are externally declared, not learned/validated |
| Sequential / adaptive validity | 14 | 80% | 11.20 | predictable-IPW case closed; arbitrary adaptive search/nonstationarity not closed |
| Calibration / estimated VOC risk control | 10 | 82% | 8.20 | conformal primitives exist; no client-distribution calibration evidence |
| Causal countermodels / identifiability | 12 | 78% | 9.36 | structural authority exists; broad identifiability remains conditional |
| Decision stability / removable-compute theory | 10 | 90% | 9.00 | certified suffix theorem is narrow; general DAG compute-removability not solved |
| Pareto / economic statistical inference | 10 | 86% | 8.60 | paired simultaneous gate exists; strong external same-workload benchmark unresolved |
| Executable falsification / proof obligations | 8 | 92% | 7.36 | math attacks exist; no independent proof assistant / external formal review |
| Nonstationarity / generalization theory | 6 | 55% | 3.30 | no validated drift model or distribution-shift client guarantee |
| External theorem review / novelty boundary | 4 | 25% | 1.00 | prior art mapped, but no systematic theorem-by-theorem external review |
| **TOTAL** | **100** |  | **81.10%** | |

## Canonical score

\[
\boxed{M_{math}=81.1\%}
\]

Status: `MATHEMATICALLY_HARDENED_RESEARCH_SYSTEM`, not `FORMALLY_COMPLETE`.

The previous ~95% estimate is rejected as insufficiently grounded. The user's criticism that the earlier state was closer to ~73% is directionally correct: the v1 system had strong definitions and finite synthetic theorems but lacked explicit ambiguity robustness, adaptive importance-weighted inference, exact credal semantics, conformal risk control and simultaneous Pareto authority.

## Promotion to >=90%

Requires all of:

1. a valid general adaptive-selection inference contract or a formally justified restricted production sampling policy;
2. nonstationarity/change-point/drift handling with coverage guarantees;
3. client-distribution estimated-VOC calibration and risk control;
4. continuous/high-dimensional ambiguity model with validated metric/geometry;
5. formal multi-step VOC approximation-error bounds;
6. external theorem review / systematic prior-art equivalence audit;
7. no surviving mathematical mutation/falsification attacks.

Without those, reporting `>=90% mathematics complete` is prohibited.
