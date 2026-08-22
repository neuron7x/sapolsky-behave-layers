# DGC Mathematics Maturity — Weighted Evidence Rubric

Date: 2026-08-22

This score measures **coverage of mathematical obligations**, not probability that DGC is true, commercially successful, or novel.

\[
M=\sum_j w_j s_j,\qquad \sum_j w_j=100,\qquad s_j\in[0,1].
\]

A dimension receives 100% only when definitions, assumptions, failure conditions, executable checks and relevant empirical/calibration obligations are materially closed.

| Dimension | Weight | Current score | Weighted points | Why not 100% |
|---|---:|---:|---:|---|
| Decision theory / VOI / VOC semantics | 12 | 95% | 11.40 | exact finite oracle and PI upper bounds exist; scalable multi-step control remains approximate |
| Robustness / ambiguity / misspecification | 14 | 86% | 12.04 | ambiguity geometry and robustness budgets remain externally declared |
| Sequential / adaptive validity | 14 | 84% | 11.76 | restricted predictable-propensity production policy now explicit; arbitrary adaptive search remains open |
| Calibration / estimated VOC risk control | 10 | 82% | 8.20 | conformal primitives exist; no client-distribution calibration evidence |
| Causal countermodels / identifiability | 12 | 82% | 9.84 | declared-query obligation certificate is fail-closed; general graphical identification remains unsolved |
| Decision stability / removable-compute theory | 10 | 90% | 9.00 | certified suffix theorem is narrow; general DAG compute-removability not solved |
| Pareto / economic statistical inference | 10 | 86% | 8.60 | paired simultaneous gate exists; strong external same-workload benchmark unresolved |
| Executable falsification / proof obligations | 8 | 95% | 7.60 | v2/v2b/v2c attacks exist; no proof assistant or independent formal review |
| Nonstationarity / generalization theory | 6 | 72% | 4.32 | bounded-drift independent case closed; unknown/dependent/adversarial drift remains open |
| External theorem review / novelty boundary | 4 | 38% | 1.52 | foundational prior art mapped; no independent theorem-by-theorem review |
| **TOTAL** | **100** |  | **84.28%** | |

## Canonical score

\[
\boxed{M_{math}=84.3\%}
\]

Status: `MATHEMATICALLY_HARDENED_RESEARCH_SYSTEM`, not `FORMALLY_COMPLETE`.

The previous ~95% estimate is rejected. The earlier ~73% criticism was directionally sound: v1 lacked explicit model-misspecification robustness, adaptive-valid inference, credal semantics, risk control, Pareto authority, nonstationary treatment and a nonmyopic metareasoning boundary.

## Promotion to >=90%

Requires material closure of all of:

1. validity for a production-grade adaptive policy under logged predictable propensities, or a justified stronger adaptive theorem;
2. unknown/change-point/dependent/adversarial drift beyond externally certified bounded drift;
3. client-distribution estimated-VOC calibration and risk control;
4. continuous/high-dimensional ambiguity with validated metric/geometry;
5. useful scalable multi-step VOC approximation-error bounds tighter than the perfect-information ceiling;
6. broader causal identification/transport beyond declared-query obligation checks;
7. independent theorem-by-theorem review or proof-assistant verification of critical propositions;
8. no surviving mathematical mutation/falsification attacks.

Without these, reporting `>=90% mathematics complete` is prohibited.
