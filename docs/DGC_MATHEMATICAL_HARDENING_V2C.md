# DGC Mathematical Hardening v2c — Restricted Adaptation, Drift and Meta-Gap Bounds

Status: executable narrow theorems; **not** a general solution to adaptive metareasoning or nonstationarity.

## P17 — Current-mean bound under externally certified bounded drift

For independent `X_i in [L,H]`, let `mu_i=E[X_i]` and let an external authority certify `|mu_i - mu_T| <= d_i`. Hoeffding gives, with probability at least `1-delta`, `avg(mu_i) >= avg(X_i) - (H-L)*sqrt(log(1/delta)/(2n))`. Because `mu_T >= avg(mu_i) - avg(d_i)`, a valid lower bound is `LCB_T = avg(X_i) - radius - avg(d_i)` clipped to `[L,H]`.

This theorem does **not** cover arbitrary dependence, hidden post-hoc drift budgets, or adversarially invalid envelopes.

## P18 — Restricted adaptive production sampling contract

DGC may use adaptive importance-weighted sequential inference only when: one target distribution `q` is frozen before sampling; selection propensities are predictable before observing the selected outcome; every positive-target item retains `pi_t(i) >= pi_min > 0`; and hidden filtering/outcome-dependent propensity rewriting is prohibited. Then `q(i)/pi_t(i) <= max_i q(i)/pi_min`, giving an explicit importance-weight cap usable by the existing e-process.

## P19 — Perfect-information upper bound on myopic meta-reasoning error

For finite pure-information compute, expected regret of the current external action upper-bounds the gross value of any information sequence. If `EVPI_upper` is valid over the relevant ambiguity set and every future sequence costs at least `c_min`, then `V_global <= EVPI_upper - c_min`. For a myopic value `V_myopic`, `0 <= V_global - V_myopic <= max(0, EVPI_upper - c_min - V_myopic)`.

This is a deliberately loose safety ceiling. It is not a tight scalable approximation theorem for general metalevel MDPs.

## P20 — Causal-identifiability obligation certificate

The runtime distinguishes **declared-query authority** from general identifiability. A DGC causal computation is not admitted as identified unless structural-model identity, intervention, outcome mapping, confounding assumptions, and transport assumptions (when needed) are explicitly declared. Passing this checker does not replace do-calculus or prove identification in arbitrary DAGs.

## Prior-art boundary

Rational metareasoning and value-of-computation predate DGC (Russell & Wefald; Hay et al.). The contribution here is an executable governance composition and explicit failure boundaries, not a novelty claim over VOC itself.
