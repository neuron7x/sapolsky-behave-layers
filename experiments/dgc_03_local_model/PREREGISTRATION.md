# DGC-03 — Real-Data Small-Local-Model Compute-Admission Pilot

Date frozen: 2026-08-22
Status: PRE-EXECUTION / NO DGC-03 PRIMARY OR REPLICATION OUTPUT OBSERVED
Lineage: DGC compute-governance hypothesis; **not** a rescue of the closed CWC-FLAGSHIP-ROUTE-02 learned-routing programme.

## Question

On the already frozen real-data, two-exit byte-level Transformer workload, can a conservative DGC compute-admission rule skip the second Transformer block while preserving observed next-token cross-entropy relative to fixed depth-2 and reducing logical FLOPs by at least 30%?

Secondary question: on exactly the same rows, does DGC Pareto-dominate the existing full-calibration point-estimate decision-relevant router from CWC-FLAGSHIP-ROUTE-02?

## Frozen substrate

No base model is trained or modified by DGC-03.

- source workload: `artifacts/wp18-real-workload-pilot/`;
- model/checkpoint authority: `artifacts/cwc-flagship-route-02/checkpoints/`;
- seeds PRIMARY: 74401, 74402, 74403;
- seeds REPLICATION: 74501, 74502, 74503;
- families: PROSE, CODE;
- model: byte vocabulary 256, sequence length 64, d_model 64, 4 heads, 2 Transformer blocks;
- scientific rows use the already frozen R2 non-overlapping PRIMARY/REPLICATION windows.

Any checkpoint/data SHA mismatch makes the experiment `NOT_EXECUTABLE`.

## Information boundary

At admission time DGC may observe only the depth-1 representation already authorized by R2:

`z = concat(mean_t(h1[t,:]), family_indicator)`.

It may not observe the target, loss1/loss2, depth-2 state, file identity, offset, realized gain, cohort identity, or oracle label.

## Calibration split

For each model seed, R2 CALIBRATION rows are deterministically split by SHA-256 of `DGC-03|case_id`:

- FIT if integer hash mod 3 is 0 or 1;
- BOUND if integer hash mod 3 is 2.

A ridge model with the already frozen `alpha=1e-3` is fit on FIT rows only to predict per-window gain `loss1-loss2`.

The one-sided residual lower offset is frozen at `alpha=0.10`. For BOUND residuals `r_i = gain_i - pred_i`, sort ascending and take order statistic

`k = max(1, floor(alpha * (n_bound + 1)))` (1-indexed).

The admission lower score is

`LCB_gain(x) = pred_gain(x) + r_(k)`.

This is a split-conformal-style marginal lower bound under exchangeability. Because PRIMARY/REPLICATION are different files, DGC-03 does **not** assume exchangeability under file shift; coverage is reported diagnostically and never used as an unqualified guarantee.

## Compute-value threshold

For each family/seed, FIT rows determine a non-negative loss-per-FLOP exchange rate

`lambda = max(0, (mean_loss1_fit - mean_loss2_fit) / block2_logical_FLOPs)`.

The next computation (block 2) is admitted iff

`LCB_gain > lambda * block2_logical_FLOPs`.

No threshold search, alpha search, feature search, seed replacement, row dropping or post-result calibration is allowed.

## Baselines

On each identical scientific cell report:

1. FIXED_DEPTH_1;
2. FIXED_DEPTH_2;
3. FIXED_FRONTIER at DGC compute;
4. POINT_SAME_SPLIT (same ridge/FIT data, point prediction > cost threshold);
5. R2_FULL_CALIBRATION_POINT (existing R2 policy, stronger calibration-data baseline);
6. RANDOM_MATCHED at DGC continuation count;
7. ORACLE_MATCHED at DGC continuation count (diagnostic upper bound only);
8. DGC_CONSERVATIVE_LCB.

## Primary metrics

For each policy:

- observed mean cross-entropy;
- logical FLOPs/window;
- compute saving vs FIXED_DEPTH_2;
- `DeltaQuality_vs_depth2 = CE_depth2 - CE_policy` (positive is better);
- continuation rate.

Cohort metrics pool all six seed/family cells with equal row weight.

## Frozen 30% local-model gate

`LOCAL_MODEL_30PCT_MET` requires independently in PRIMARY and REPLICATION:

1. `Savings_vs_depth2 >= 0.30`;
2. `DeltaQuality_vs_depth2 >= 0`;
3. coverage = 1.0 (no row/seed dropping);
4. no information-boundary violation;
5. all data/checkpoint integrity checks pass.

Failure of either cohort is `LOCAL_MODEL_30PCT_NOT_SUPPORTED`.

This is finite-workload evidence only; it does not imply OpenAI/Anthropic/client savings.

## Strong internal-router gate

DGC Pareto-dominates `R2_FULL_CALIBRATION_POINT` in a cohort iff:

- DGC FLOPs <= R2 FLOPs;
- DGC CE <= R2 CE;
- at least one inequality is strict.

`DGC_BEATS_INTERNAL_POINT_ROUTER` requires dominance in both PRIMARY and REPLICATION. Otherwise status is `NOT_SUPPORTED` or `INCOMPARABLE` exactly as observed.

This is **not** the external 2026 frontier-router claim; Avengers-Pro/LLMRouterBench still requires a separate same-model-pool benchmark.

## Negative-result rule

All outcomes are retained. A failure cannot be repaired by changing alpha, split, threshold, seed, model, family, or metric under DGC-03.
