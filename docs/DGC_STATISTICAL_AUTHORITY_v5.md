# DGC Statistical Authority v5.1

Status: **pre-execution mathematical contract**. This document does not assert that DGC passes the contract.

## 1. Claim decomposition

DGC intentionally separates five propositions:

1. exact facts about a completely observed frozen panel;
2. time-uniform inference about the average conditional mean of a precommitted bounded sequence;
3. shift-panel evidence across preregistered G1-G5 axes;
4. fresh independently attested replication;
5. global two-family product qualification.

No proposition is allowed to substitute for another.

## 2. Exact panel fact

For baseline `b` and ordered pair index `i=(task,replicate)`:

`C_bi = physical_cost_bi - physical_cost_DGCi`

`Q_bi = quality_DGCi - quality_bi`

`R_bi = catastrophic_regret_bi - catastrophic_regret_DGCi`.

The exact realized panel passes baseline `b` iff

`mean(C_b) > 0`,

`mean(Q_b) >= -0.02`,

`mean(R_b) >= -0.01`.

All four baselines must pass. This is deterministic arithmetic and carries no stochastic or generalization interpretation.

## 3. Time-uniform average-conditional-mean inference

V5.1 uses Howard–Ramdas–McAuliffe–Sekhon Theorem 4 composed with the exact polynomial-stitching boundary of Eq. (10).

The estimand at time `t` is

`mu_bar_t = t^-1 * sum_i E[X_i | F_{i-1}]`.

The observations may be non-identically distributed and adapted. DGC does not require an iid population-mean interpretation or provider-request independence for this primary confidence-sequence claim.

A predictable center is frozen before each observation:

`Xhat_t = (1/2 + sum_{j<t} X_j) / t`

after rescaling the bounded observation to `[0,1]`.

The variance process is

`V_t = sum_i (X_i - Xhat_i)^2`.

The executable theorem identity is:

- inference: `HOWARD_RAMDAS_MCAULIFFE_SEKHON_THEOREM4_POLY_STITCHING_EXACT_V3`;
- boundary: `HOWARD_EQ10_POLYNOMIAL_STITCHING_EXACT_V2_4deabb17370edfc7`;
- boundary-parameter SHA-256: `4deabb17370edfc770b7612235ee9dfddf932dfc21e894161fb2757ea45a1329`;
- `zeta(1.4)` binary64: `0x1.8d8292bd8c3a6p+1`;
- author reference: `gostevehoward/confseq@5ffe733ca2447a2e28c2c91f3b00086173f2ab2c`.

For desired two-sided claim error `delta`, the one-boundary crossing probability is `delta/2`. The exact polynomial boundary and binary64 parameter audit are documented in `DGC_THEOREM_AUDIT_v5.md`.

## 4. Primary multiplicity

Primary claims: two workload families × four baselines × three endpoints = 24.

`delta_primary_claim = 0.05/24`.

The corresponding one-boundary crossing level inside Theorem 4 is `0.05/48`.

Global primary familywise error is controlled by Bonferroni across the 24 two-sided claims. No cross-claim independence assumption is required for the union bound.

## 5. G1-G5 multiplicity

The separate generalization family has five axes × four baselines × three endpoints = 60 claims.

`delta_G_claim = 0.05/60`.

Each two-sided confidence sequence uses one-boundary crossing probability `0.05/120`.

`GENERALIZATION_SUPPORTED` requires exact-panel and confidence-sequence success on every preregistered axis. It means support on those five frozen shift panels, not universal generalization.

## 6. Planning versus inference

Cluster-aware variance sizing and any legacy empirical-Bernstein/Hoeffding calculations are planning or sensitivity artifacts only. They cannot authorize P9, G1-G5 or product promotion.

The V5.1 confirmatory gate is determined from exact observed raw subjects under the content-identified theorem runtime. Insufficient evidence causes failure; it cannot be repaired by post-outcome retuning.

## 7. Physical cost

Cost comparisons use verified ten-component all-in operational cost subjects, not the coordinator's budget meter. Missing or substituted physical-cost evidence prevents the cost endpoint from being evaluated.

## 8. Coverage

Primary P9 construction requires exact `task × policy × replicate` completeness and every paired baseline row has `coverage=1.0`; the exact finite-panel certificate rejects any incomplete matched population. Therefore coverage equivalence is a derived prerequisite of P9 rather than an independently asserted boolean.

## 9. Fault tolerance and replication

Fault tolerance is an independent preregistered/replayed proof obligation. Independent replication requires fresh execution, physical-cost and CCF evidence under the same frozen methodology plus a cryptographically verified external attestation. The signature proves possession/attestation, not the social fact of independence by itself.

## 10. Global product qualification

A family-level P19 root is not a global product verdict. The global authority must replay distinct P19 roots for exactly `SWE_BENCH_VERIFIED` and `TERMINAL_BENCH_2_1`, with identical repository and V5.1 methodology identities.

`PRODUCT_QUALIFIED` remains false until that complete chain exists.
