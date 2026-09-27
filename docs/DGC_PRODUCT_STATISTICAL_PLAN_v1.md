# DGC Product Statistical Plan v1

Status: `FROZEN_PRE_EXECUTION_STATISTICAL_PLAN`
Date: 2026-08-22
Implementation authority: `cwc/governance/product_statistical_plan.py` + `cwc/governance/pareto.py`

This plan is frozen before external confirmatory outcomes are inspected. It is a product-evidence protocol, not evidence that DGC already passes it.

## External workload families

The primary product experiment requires both independently sourced families frozen in `docs/DGC_EXTERNAL_WORKLOAD_PANEL_v1.md`:

1. SWE-bench Verified;
2. Terminal-Bench 2.1.

No family may be replaced after confirmatory results are observed without starting a new preregistration generation.

## Policy panel

Within each family compare DGC against all four preregistered baselines:

- B0 Fixed Compute;
- B1 Uncertainty/Entropy Router;
- B2 Learned Cost/Quality Router;
- B3 Sequential Verification.

DGC must satisfy the confirmatory gate against **every** admissible baseline on the identical paired trial population. The strongest baseline is not selected after seeing results.

## Primary confirmatory endpoints

For every family × baseline pair, compute paired observations for:

1. `baseline_total_operational_cost - DGC_total_operational_cost` — positive means DGC is cheaper;
2. `DGC_quality - baseline_quality` — positive means DGC is better;
3. `baseline_catastrophic_regret - DGC_catastrophic_regret` — positive means DGC is safer on this metric.

Total operational cost must use the full boundary in `DGC_PRODUCT_CLAIM_v1.md`, including human review, infra, retries and failure loss.

## Frozen error budget and margins

Global familywise alpha: `0.05`.

Multiplicity family:

`2 workload families × 4 baselines × 3 endpoints = 24 claims`.

Therefore the frozen per-claim allocation is:

`alpha_claim = 0.05 / 24 = 0.0020833333333333333`.

Equivalent execution: call `certify_multi_baseline_pareto_improvement` separately for each family with `alpha=0.025`; it allocates `0.025/(3×4)` to each baseline-endpoint bound.

Frozen non-inferiority margins:

- quality: `delta_Q = 0.02` on a normalized [0,1] quality scale;
- catastrophic regret: `delta_R = 0.01` on a normalized [0,1] catastrophic-regret scale.

These are protocol values for the first product experiment generation. If domain-specific scorer semantics make either margin scientifically inappropriate, the experiment must be versioned and re-preregistered **before** confirmatory outcomes are inspected; the old generation is not silently rewritten.

Minimum cost effect of interest for power sizing: `0.05` (5% normalized total-cost effect). This is not the commercial 30% target.

## Calibration / confirmatory separation

Task assignment is deterministic from task ID using SHA-256 with prefix `DGC-SPLIT-V1:`.

- 20% calibration tasks;
- 80% confirmatory tasks.

Calibration tasks may be used to estimate variance, validate instrumentation, choose the preregistered trial count and fit any explicitly permitted DGC estimator/router parameters.

Confirmatory task outcomes must not be inspected before policy, model pool, budgets, scorer, cost table, trial count and statistical-plan digests are frozen.

## Trial count

One run per task is not product evidence. Repeated stochastic trials are required.

Target power: `0.90`.
Minimum: `5` trials/task.
Hard preregistered ceiling: `50` trials/task for this generation.

`approximate_required_trials_per_task` uses calibration-only variance and the frozen familywise error allocation to choose the count. It is a planning calculation, not the confirmatory hypothesis test.

If the estimated required count exceeds 50, the generation is `UNDERPOWERED`; the evidence standard must not be weakened post hoc. A new preregistration may alter resources/design before confirmatory execution.

## Confirmatory inference

Primary confirmatory inference is finite-sample bounded paired inference implemented by `certify_multi_baseline_pareto_improvement`.

Within each family, all baselines must have:

- the same `paired_task_digest`;
- the same paired sample count;
- full matched coverage;
- preregistered finite supports for cost, quality and catastrophic-regret differences.

The implementation uses Hoeffding mean bounds plus Bonferroni/union-bound control. Independence across metrics or baselines is not required for the multiplicity guarantee; validity still requires the declared bounded-observation/sampling assumptions.

## Scientific success gate

For **both** external families and **all four** baselines:

- cost lower bound > 0;
- quality lower bound >= `-0.02`;
- catastrophic-regret lower bound >= `-0.01`;
- full paired coverage;
- identical frozen harness except governance policy.

Only then may `external_real_workload_supported`, quality/regret non-inferiority and net-cost-superiority evidence be considered for promotion.

## Commercial target

`NetSaving >= 30%` remains a separate commercial target. It is evaluated only after scientific quality/regret/coverage gates pass and all operational overhead is included. Failure to reach 30% does not erase a smaller statistically supported scientific cost advantage; conversely, a 30% point estimate without the confirmatory evidence chain does not authorize a commercial claim.

## Generalization and independent replication

This primary plan does not itself satisfy product qualification. After a successful primary experiment, the frozen DGC policy must still be tested for unseen task/domain/model/economic shifts and independently replicated according to the evidence-to-product protocol.
