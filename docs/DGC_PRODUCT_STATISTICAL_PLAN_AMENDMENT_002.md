# DGC Product Statistical Plan — Pre-Execution Amendment 002

Date: 2026-08-23
Status: `PRE_EXECUTION / NO_CONFIRMATORY_OUTCOMES_OBSERVED`

## Reason for amendment

The V1 repeated-trial sizing helper used a pooled IID normal approximation and divided the implied sample requirement by the number of confirmatory tasks. For stochastic agent benchmarks, repeated trials are nested within tasks; treating within-task repetitions as independent task draws can create pseudoreplication and overstate power when task heterogeneity is material.

No SWE-bench Verified or Terminal-Bench 2.1 DGC confirmatory outcomes have been executed in this evidence generation. The amendment therefore changes the plan **before** confirmatory outcome inspection and does not respond to observed product results.

## V2 frozen sizing model

For the paired endpoint difference D, use calibration-only variance components:

`Var(mean(D)) = sigma_between^2 / N_tasks + sigma_within^2 / (N_tasks * R)`

where:

- `N_tasks` is the frozen confirmatory task count;
- `R` is repeated trials per task;
- `sigma_between` is a calibration-only estimate of between-task heterogeneity;
- `sigma_within` is a calibration-only estimate of within-task stochastic variability.

The target standard error is

`effect_of_interest / (z_(1-alpha_claim) + z_power)`.

## Fail-closed consequences

1. If the between-task variance floor alone exceeds the target variance, return `UNDERPOWERED_TASK_HETEROGENEITY`. Increasing R is not allowed to manufacture power.
2. Otherwise solve the minimum R required for the within-task term, apply the preregistered minimum floor and hard maximum cap.
3. If R exceeds the hard cap, return `UNDERPOWERED`.
4. Variance components must be estimated from calibration tasks only.
5. The legacy pooled-IID helper remains in code only for historical/research analyses and is **not authorized** for Product Qualification V2.

## Unchanged evidence standards

- global familywise alpha: 0.05;
- 2 workload families × 4 baselines × 3 endpoints;
- quality noninferiority margin: 0.02;
- catastrophic-regret noninferiority margin: 0.01;
- minimum cost effect of interest: 0.05;
- calibration fraction: 0.20;
- target power: 0.90;
- minimum repeated trials/task: 5;
- maximum repeated trials/task: 50;
- confirmatory tasks remain disjoint from calibration tasks;
- no post-hoc lowering of alpha, margins or baseline strength.

## New plan identifier

`DGC_PRODUCT_PAIRED_CLUSTER_AWARE_V2`

This amendment supersedes V1 for future product-qualification execution. It does not retroactively alter any earlier synthetic/narrow experiments.
