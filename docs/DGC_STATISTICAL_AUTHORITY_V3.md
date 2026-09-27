# DGC Statistical Authority V3

Status: **pre-execution mathematical protocol**. This document does not assert that DGC passes the protocol.

## 1. Two evidence statements, one scientific gate

DGC separates two statements that must never be conflated.

### A. Exact frozen finite-panel fact

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

### B. Conditional expected-effect support

The frozen product protocol also requires bounded inferential support, not only a favorable point estimate.

For independent bounded variables `X_1,...,X_n` with possibly different distributions, Maurer & Pontil (2009), Theorem 11 gives the empirical-Bernstein lower confidence form

`E[mean(X)] >= mean(X) - sqrt(2 V_n log(2/delta)/n) - 7 L log(2/delta)/(3(n-1))`,

where

- `V_n = (1/(n-1)) Σ_i (X_i - mean(X))²` is the sample variance;
- `L = upper_support - lower_support`;
- `n >= 2`.

DGC applies the lower bound separately to cost gain, quality gain and catastrophic-regret gain.

Authority: `MAURER_PONTIL_THEOREM_11_EMPIRICAL_BERNSTEIN_LOWER_V1`.

Reference: Andreas Maurer and Massimiliano Pontil, *Empirical Bernstein Bounds and Sample Variance Penalization*, COLT 2009, arXiv:0907.3740.

The scientific gate is the conjunction:

`exact frozen-panel PASS ∧ conditional bounded-inference PASS under the frozen assumptions`.

The exact certificate prevents a statistical procedure from obscuring what actually happened on the executed panel. The confidence certificate prevents a favorable but statistically unsupported point estimate from being promoted as P9 support.

## 2. Pairing and dependence boundary

A single inferential observation is the paired difference for one `(task, replicate, baseline)` comparison. Baseline and DGC outputs inside a pair may be dependent; common-random-number pairing is allowed and can reduce paired variance.

The empirical-Bernstein theorem requires independence **across paired observation indices** for the baseline/endpoint being bounded. Identical distribution is not required.

Dependence across baselines or endpoints does not invalidate the familywise guarantee because DGC uses a Bonferroni union bound; Bonferroni does not assume independence between claims.

Machine-verifiable execution evidence establishes:

- preregistered paired seed schedule;
- the same seed across policies within `(task, replicate)`;
- unique provider request IDs across work units;
- full task × policy × replicate coverage.

It does **not** prove provider-internal stochastic independence. Therefore the expected-effect certificate is explicitly conditional on

`CROSS_TASK_REPLICATE_PROVIDER_REQUESTS_CONDITIONALLY_INDEPENDENT`.

`randomness_assumption_verified=false` remains an explicit field unless independent external evidence establishes more. This does not affect the deterministic exact-panel fact; it does define the assumption boundary of the confidence statement.

## 3. Multiplicity

Primary P9 freezes two workload families, four baselines and three endpoints.

With global `alpha = 0.05`, family alpha is

`alpha_family = 0.05 / 2 = 0.025`.

Within one workload family,

`delta_claim = 0.025 / (4 × 3) = 0.05 / 24 ≈ 0.0020833333333333333`.

The union bound therefore controls the preregistered 24 primary baseline-endpoint claims at global familywise error at most 0.05, conditional on validity of each component confidence bound.

For G1-G5, a separately frozen generalization family allocates

`delta_G = 0.05 / (5 × 4 × 3) = 1/1200 ≈ 0.0008333333333333334`.

No independence between the 60 G1-G5 claims is required for Bonferroni control.

## 4. Why replicates are no longer averaged away

The superseded path averaged all `R` repetitions inside each task and then applied a support-only Hoeffding bound over `N_tasks` points. That discarded most inferential value of repeated executions.

V3 uses the complete paired `(task, replicate)` population. Thus

`n = N_tasks × R`.

The empirical-Bernstein width depends on observed variance and decreases with the number of independent paired observations. This makes the inferential authority consistent with actually paying for repeated executions.

Equal `R` is required for every task/policy cell, so equal task × replicate weighting does not silently reweight tasks.

## 5. Cluster-aware sizing is planning, not the final theorem

The existing planning model

`Var(mean) = sigma_between²/N_tasks + sigma_within²/(N_tasks × R)`

is useful when reasoning about a task-superpopulation estimand and prevents pretending that repetitions create new task diversity.

It is **not** the theorem used for the frozen finite-panel confidence bound.

Accordingly:

- cluster-aware sizing remains `planning_only=true`;
- `UNDERPOWERED_TASK_HETEROGENEITY` remains a conservative planning/generalization warning;
- final P9 support is recomputed from the complete observed confirmatory panel;
- empirical-Bernstein planning uses a calibration-derived variance proxy only to estimate resource needs;
- if confirmatory variance is worse than the proxy, the final gate fails rather than revising the protocol post hoc.

The frozen `minimum_cost_effect_of_interest = 0.05` is likewise a **planning/power-sizing value**, not the P9 scientific cost threshold. The frozen statistical plan defines the scientific cost gate as lower confidence bound `> 0`; the separate 30% saving target remains commercial, not scientific.

## 6. Empirical-Bernstein planning equation

For variance proxy `v`, support range `L`, target half-width `w`, and claim error `delta`, V3 chooses the smallest total `n` satisfying

`sqrt(2 v log(2/delta)/n) + 7 L log(2/delta)/(3(n-1)) <= w`.

For a frozen panel of `N_tasks`, the corresponding repetition count is

`R = ceil(n / N_tasks)`

subject to the preregistered maximum-R cap.

This calculation is a **planning forecast, not a power guarantee**, because confirmatory sample variance is unknown before execution. Final inference always uses the observed confirmatory variance.

## 7. P9 promotion semantics

`P9_SUPPORTED` requires all of:

1. exact complete execution and physical-cost populations;
2. exact frozen-panel Pareto/noninferiority success against B0-B3;
3. empirical-Bernstein lower-bound support against B0-B3 under the frozen independence assumption;
4. exact frozen multiplicity allocation;
5. complete CCF headroom audit;
6. digest/lineage equality under raw-subject replay.

Neither component can rescue the other:

- exact PASS + confidence FAIL → `P9_SUPPORTED=false`;
- exact FAIL + confidence PASS → `P9_SUPPORTED=false`.

The conditional nature of the confidence claim remains explicit; `randomness_assumption_verified=false` is not silently converted into theorem-free certainty.

## 8. G1-G5 promotion semantics

`GENERALIZATION_SUPPORTED` uses the same scientific conjunction for every preregistered shift axis:

`Gk exact panel PASS ∧ Gk empirical-Bernstein PASS`, for every `k ∈ {1,...,5}`.

All five axes must pass, under their frozen source/model/pricing/perturbation identities, without policy retuning.

This supports only the five preregistered generalization panels. It does **not** establish universal generalization.

## 9. Downstream boundary

`INDEPENDENT_REPLICATION_SUPPORTED` must be established from a fresh externally attributable execution/review subject; self-replay cannot satisfy it.

`PRODUCT_QUALIFIED` remains false until independent replication, P19 sealing and all other product-evidence obligations are actually satisfied.
