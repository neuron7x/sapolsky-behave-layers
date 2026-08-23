# DGC Statistical Authority V3

Status: **pre-execution mathematical protocol**. This document does not assert that DGC passes the protocol.

## 1. Two claims, not one

DGC separates two different estimands that must never be conflated.

### A. Exact frozen finite-panel claim

For each baseline `b ∈ {B0,B1,B2,B3}` and each preregistered pair index `i=(task, replicate)`, define

- `C_bi = physical_cost_bi - physical_cost_DGCi`
- `Q_bi = quality_DGCi - quality_bi`
- `R_bi = catastrophic_regret_bi - catastrophic_regret_DGCi`

over the **complete frozen task × replicate population**.

The exact panel passes baseline `b` iff

`mean(C_b) > 0`,

`mean(Q_b) >= -m_quality`,

`mean(R_b) >= -m_catastrophic`.

All four baselines must pass simultaneously. This is deterministic arithmetic over the complete executed panel. It contains **no confidence level, p-value, iid assumption or generalization claim**.

Authority: `EXACT_FROZEN_FINITE_PANEL_PARETO_V1`.

### B. Conditional expected-effect claim

For the same frozen pair population, the system may additionally ask whether the mean expected paired effect is supported under the declared cross-pair independence assumption.

For independent bounded variables `X_1,...,X_n` with possibly different distributions, Maurer & Pontil (2009), Theorem 11 gives the empirical-Bernstein lower confidence form

`E[mean(X)] >= mean(X) - sqrt(2 V_n log(2/delta)/n) - 7 L log(2/delta)/(3(n-1))`,

where

- `V_n = (1/(n-1)) Σ_i (X_i - mean(X))²` is the sample variance,
- `L = upper_support - lower_support`,
- `n >= 2`.

DGC applies the lower bound separately to cost gain, quality gain and catastrophic-regret gain.

Authority: `MAURER_PONTIL_THEOREM_11_EMPIRICAL_BERNSTEIN_LOWER_V1`.

Reference: Andreas Maurer and Massimiliano Pontil, *Empirical Bernstein Bounds and Sample Variance Penalization*, COLT 2009, arXiv:0907.3740.

## 2. Pairing and dependence boundary

A single observation is the paired difference for one `(task, replicate, baseline)` comparison. Baseline and DGC outputs inside a pair may be dependent; common-random-number pairing is allowed and can reduce paired variance.

The empirical-Bernstein theorem requires independence **across paired observation indices** for the baseline/endpoint being bounded. Identical distribution is not required.

Dependence across baselines or endpoints does not invalidate the familywise guarantee because DGC uses a Bonferroni union bound; Bonferroni does not assume independence between claims.

Machine-verifiable evidence currently establishes:

- preregistered paired seed schedule;
- same seed across policies within `(task, replicate)`;
- unique provider request IDs across work units;
- full task × policy × replicate coverage.

It does **not** prove provider-internal stochastic independence. Therefore the expected-effect certificate is explicitly conditional on

`CROSS_TASK_REPLICATE_PROVIDER_REQUESTS_CONDITIONALLY_INDEPENDENT`.

The exact finite-panel certificate does not depend on that assumption.

## 3. Multiplicity

Primary P9 freezes two workload families, four baselines and three endpoints.

With global `alpha = 0.05`, family alpha is

`alpha_family = 0.05 / 2 = 0.025`.

Within one workload family,

`delta_claim = 0.025 / (4 × 3) = 0.05 / 24 ≈ 0.0020833333333333333`.

The union bound therefore controls the preregistered 24 primary baseline-endpoint claims at global familywise error at most 0.05, conditional on validity of each component confidence bound.

For G1-G5, a separate frozen generalization family allocates

`delta_G = 0.05 / (5 × 4 × 3) = 1/1200 ≈ 0.0008333333333333334`.

No independence between the 60 G1-G5 claims is required for Bonferroni control.

## 4. Why replicates are no longer averaged away

The old path averaged all `R` repetitions inside each task and then applied a support-only Hoeffding bound over `N_tasks` points. That discarded most of the inferential value of repeated executions.

V3 uses the complete paired `(task, replicate)` population. Thus

`n = N_tasks × R`.

The empirical-Bernstein width depends on observed variance and decreases with the number of independent paired observations. This makes the statistical authority consistent with actually paying for repeated executions.

## 5. Cluster-aware sizing is planning, not the final theorem

The existing planning model

`Var(mean) = sigma_between²/N_tasks + sigma_within²/(N_tasks × R)`

is useful when reasoning about a task-superpopulation estimand and prevents pretending that repetitions create new task diversity.

It is **not** the theorem used for the exact frozen-panel P9 claim.

Accordingly:

- cluster-aware sizing remains `planning_only=true`;
- `UNDERPOWERED_TASK_HETEROGENEITY` remains a conservative planning/generalization warning;
- final primary P9 authority is determined from the complete observed frozen panel;
- empirical-Bernstein planning uses a calibration-derived variance proxy only to estimate resource needs;
- if confirmatory variance is worse than the proxy, the final gate fails rather than revising the protocol post hoc.

## 6. Empirical-Bernstein planning equation

For variance proxy `v`, support range `L`, target half-width `w`, and claim error `delta`, V3 chooses the smallest total `n` satisfying

`sqrt(2 v log(2/delta)/n) + 7 L log(2/delta)/(3(n-1)) <= w`.

For a frozen panel of `N_tasks`, the corresponding repetition count is

`R = ceil(n / N_tasks)`

subject to the preregistered maximum-R cap.

This calculation is a **planning forecast**, not a power guarantee, because confirmatory sample variance is unknown before execution.

## 7. Promotion semantics

`P9_SUPPORTED` requires:

1. exact complete execution and physical-cost populations;
2. exact frozen-panel Pareto/noninferiority success against B0-B3;
3. complete CCF headroom audit;
4. digest/lineage equality under raw-subject replay.

The conditional empirical-Bernstein result is retained as an additional scientific field. It is not allowed to convert an exact-panel failure into a PASS.

`GENERALIZATION_SUPPORTED` uses the same dual structure for G1-G5: exact frozen-axis panels are the stage gate; conditional expected-effect certificates remain separately labeled.

`PRODUCT_QUALIFIED` remains false until the downstream independent-replication, P19 and operational gates are actually satisfied.
