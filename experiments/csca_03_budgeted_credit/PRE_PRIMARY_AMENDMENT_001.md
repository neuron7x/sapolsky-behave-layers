# PRE-PRIMARY AMENDMENT 001

Frozen before CSCA-03 PRIMARY in the original execution attempt and preserved during deterministic recovery.

1. `budget` denotes requested counterfactual path-evaluation budget. Cached factual output adds one evaluator call. Matched primary estimators have identical actual calls; exploratory double-antithetic may exceed the smallest request because one quartet is indivisible.
2. E2 direction is evaluated from binary-centered directional leverage `phi_A/A = phi_A*A`, not raw local `phi_A`; raw local attribution sign confounds coefficient sign with factual `A` sign.
3. A 32-seed ×64-row/context calibration exceeded the available execution window before emitting a result. Before any PRIMARY result existed, the preregistered fail-closed clause was invoked and `rows_per_context=8` was frozen for CALIBRATION, PRIMARY and REPLICATION. No estimator, budget, threshold, family or seed range changed.
4. Confirmatory cohorts are executed in deterministic 8-seed chunks to avoid monolithic timeout. Chunking is an execution partition only and changes no scientific unit, seed, estimator or metric.
