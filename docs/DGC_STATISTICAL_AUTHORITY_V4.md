# DGC Statistical Authority V4

Status: **FROZEN_PRE_EXECUTION_MATHEMATICAL_PROTOCOL**. No external confirmatory outcome is asserted by this document.

## 1. Claim hierarchy

DGC V4 separates three objects that must not be conflated.

### A. Exact executed-panel fact

For baseline `b`, task `t`, replicate `r`:

- `C_btr = physical_cost_btr - physical_cost_DGC,tr`;
- `Q_btr = quality_DGC,tr - quality_btr`;
- `R_btr = catastrophic_regret_btr - catastrophic_regret_DGC,tr`.

Over the complete frozen `task × replicate` panel, baseline `b` passes the deterministic panel gate iff

`mean(C_b) > 0`,

`mean(Q_b) >= -0.02`,

`mean(R_b) >= -0.01`.

All B0-B3 baselines must pass. This is arithmetic over the executed finite panel. It carries no probability, iid or extrapolation statement.

Authority: `EXACT_FROZEN_FINITE_PANEL_PARETO_V1`.

### B. Primary nonparametric inferential claim

The primary probabilistic target is the **average conditional mean** of each precommitted bounded paired-difference sequence. V4 uses a time-uniform empirical-Bernstein confidence sequence derived from nonnegative-supermartingale concentration.

For normalized observations `X_i ∈ [0,1]`, choose a predictable center

`Xhat_i = (0.5 + sum_{j<i} X_j) / i`,

and define

`Vhat_t = max(1, sum_{i<=t} (X_i - Xhat_i)^2)`.

V4 freezes `eta=2`, `s=1.4`, `zeta(s)=3.1055472779775815` and

`H_t = s log log(eta Vhat_t) + log( 2 zeta(s) / (alpha log(eta)^s) )`,

`k1 = (eta^(1/4) + eta^(-1/4)) / sqrt(2)`,

`k2 = (sqrt(eta) + 1) / 2`.

The terminal slice of the time-uniform confidence sequence is

`Xbar_t ± [k1 sqrt(Vhat_t H_t) + k2 H_t] / t`,

then affine-rescaled back to the endpoint's frozen support.

The target is

`mu_bar_t = t^(-1) sum_{i<=t} E[X_i | F_{i-1}]`.

Therefore V4 does **not** require iid observations or independence between provider requests. The required mathematical boundary is a bounded adapted sequence with a predictable variance center and the precommitted analysis ordering.

Primary authority: `HOWARD_RAMDAS_MCAULIFFE_SEKHON_EMPIRICAL_BERNSTEIN_CS_V1`.

Reference authority: Steven R. Howard, Aaditya Ramdas, Jon McAuliffe, Jasjeet Sekhon, *Time-uniform, nonparametric, nonasymptotic confidence sequences*, Annals of Statistics 49(2), 1055-1080, 2021, DOI `10.1214/20-AOS1991`.

A 2025 preprint by Ben Chugg and Aaditya Ramdas develops tighter closed-form empirical-Bernstein confidence sequences for time-varying average conditional means. It is tracked as a future efficiency/sensitivity candidate, not silently substituted for the frozen V4 primary theorem.

### C. Legacy independence-sensitive sensitivity analysis

Maurer-Pontil empirical-Bernstein lower bounds remain computed as a secondary diagnostic because they are variance-sensitive and permit independent non-identically distributed observations. They are **not** the V4 promotion theorem because machine-verifying distinct request IDs and seeds does not prove stochastic independence inside a provider.

Reference: Andreas Maurer, Massimiliano Pontil, *Empirical Bernstein Bounds and Sample Variance Penalization*, COLT 2009, arXiv `0907.3740`.

## 2. Multiplicity

Primary P9 has

`2 workload families × 4 baselines × 3 endpoints = 24 claims`.

Global familywise alpha is `0.05`, so each primary confidence sequence uses

`alpha_claim = 0.05 / 24 = 0.0020833333333333333`.

Bonferroni control requires no independence between endpoints or baselines.

The G1-G5 generalization family contains

`5 axes × 4 baselines × 3 endpoints = 60 claims`,

so

`alpha_G = 0.05 / 60 = 0.0008333333333333334`.

Each per-claim interval is itself time-uniform; the union bound therefore remains valid under repeated inspection/stopping within each claim's sequence.

## 3. Analysis sequence

The analysis ordering is outcome-independent and frozen as

`TASK_ID_ASC_THEN_REPLICATE_ASC`.

The order is part of the authority digest. It is not selected after outcomes.

Because the primary target is an average conditional mean, dependence and nonstationarity are represented in the conditional means rather than hidden behind an iid assumption.

## 4. Why repetitions remain useful without pseudo-replication

V4 does not claim that `N_tasks × R` observations are independent. Each paired observation contributes to the adapted bounded sequence used by the confidence sequence. The supermartingale validity is not obtained by counting them as iid draws.

Cluster-aware variance decomposition remains useful for **resource planning and task-diversity diagnostics**, not as the final proof theorem:

`Var(mean) ≈ sigma_between^2/N_tasks + sigma_within^2/(N_tasks R)`.

No planning approximation may substitute for the observed confirmatory confidence sequence.

## 5. Primary P9 scientific gate

For each workload family and every baseline B0-B3, all conditions must hold:

1. complete frozen execution population;
2. complete ten-component physical-cost accounting;
3. exact finite-panel cost/quality/regret gate passes;
4. anytime-valid average-conditional-mean lower bound satisfies
   - cost LB `> 0`,
   - quality LB `>= -0.02`,
   - catastrophic-regret LB `>= -0.01`;
5. multiplicity allocation equals the frozen plan;
6. CCF headroom audit is complete;
7. raw-subject replay reproduces every authority digest.

A favorable exact panel cannot rescue a failed confidence sequence. A favorable confidence sequence cannot rescue an unfavorable exact panel.

## 6. G1-G5 scientific gate

Every preregistered axis G1-G5 repeats the same exact + anytime-valid structure under no-retuning semantics and frozen source/model/pricing/perturbation identities.

`GENERALIZATION_SUPPORTED` means only that the five preregistered shift panels satisfy their exact and anytime-valid gates. It is not a universal-generalization theorem.

## 7. Optional stopping / monitoring

The primary V4 confidence sequence is time-uniform. This specifically removes a failure mode in which operators repeatedly inspect intermediate results and stop when a fixed-n interval becomes favorable.

The evidence ledger still requires complete frozen populations for promotion; time-uniform validity is an additional robustness property, not permission to truncate required evidence.

## 8. Claim boundary

`PRODUCT_QUALIFIED=false` remains mandatory until real external P9, G1-G5, independent replication, P19 sealing and downstream operational requirements are actually satisfied.
