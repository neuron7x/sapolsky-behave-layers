# DGC B2 Learned Cost-Quality Router v1

Status: `ALGORITHM_IMPLEMENTED / EXTERNAL_FIT_PENDING`

## Purpose

B2 is a real learned baseline, not a label. It is designed to make DGC compete against a deterministic calibration-only cost-quality router rather than weak threshold heuristics.

## Frozen algorithm

For each allowed compute action, B2 fits a separate ridge-regression utility model on a complete calibration counterfactual table.

Declared utility:

`U = w_q * quality - w_c * cost_usd - w_r * catastrophic_regret`

The frozen configuration binds:

- ordered feature schema;
- action set;
- ridge coefficient;
- quality/cost/regret weights;
- unregularized intercept;
- lexicographic tie-break;
- training algorithm digest.

## Leakage and completeness invariants

1. Confirmatory task IDs may be supplied as forbidden IDs; any overlap with calibration is rejected.
2. Every calibration task must contain exactly one row for every frozen action.
3. Duplicate task/action pairs are rejected.
4. Unknown actions, feature-shape mismatch and non-finite values are rejected.
5. Calibration rows are canonically sorted before fitting, so input ordering does not change the model digest.
6. The fitted artifact binds both the calibration-task digest and model digest.

## Baseline-panel authority

B2 must not count as `executable_frozen` until its `BaselinePolicySpec` is bound to the same feature-schema digest, training-algorithm digest, calibration-task digest and fitted-model digest produced by the executable fit.

## Current authority

Targeted local tests: `6/6 PASS`.

Adversarial gate: `4/4 attacks killed`, covering confirmatory leakage, missing counterfactual action, duplicate task/action data and invalid quality support.

## Claim boundary

The algorithm is implemented, but it has not yet been fitted on the frozen calibration split of SWE-bench Verified / Terminal-Bench 2.1. Therefore:

`B2_ALGORITHM_IMPLEMENTED=true`

`B2_EXTERNAL_FIT_VERIFIED=false`

`BASELINE_PANEL_EXECUTABLE_FROZEN=false`
