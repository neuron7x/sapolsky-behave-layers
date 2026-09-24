# DGC Product Statistical Plan v5.1

Status: `FROZEN_PRE_EXECUTION / EXTERNAL_CONFIRMATORY_OUTCOMES_UNOBSERVED`.

## Fixed design

- canonical primary workload families: `2`;
- baselines per family: `B0`, `B1`, `B2`, `B3`;
- endpoints: physical operational cost, quality, catastrophic regret;
- global primary familywise alpha: `0.05`;
- quality noninferiority margin: `0.02`;
- catastrophic-regret noninferiority margin: `0.01`;
- minimum cost effect of interest `0.05` is a planning quantity, not a P9 acceptance threshold;
- calibration fraction: `0.20`;
- G1 unseen-task holdout fraction: `0.20`;
- primary confirmatory remainder: `0.60` subject to deterministic integer allocation;
- target planning power: `0.90`;
- frozen repeat bounds: `5 <= R <= 50`.

## Primary multiplicity

There are `2*4*3 = 24` preregistered primary family/baseline/endpoint claims.

`delta_claim = 0.05 / 24`.

For the two-sided Howard Theorem-4 confidence sequence, the one-boundary crossing probability is

`alpha_boundary = delta_claim / 2 = 0.05 / 48`.

Bonferroni does not require independence between baseline or endpoint claims.

## Primary statistical authority

The executable plan freezes:

- inference: `HOWARD_RAMDAS_MCAULIFFE_SEKHON_THEOREM4_POLY_STITCHING_EXACT_V3`;
- boundary: `HOWARD_EQ10_POLYNOMIAL_STITCHING_EXACT_V2_4deabb17370edfc7`;
- target: `AVERAGE_CONDITIONAL_MEAN_OF_PRECOMMITTED_BOUNDED_SEQUENCE`;
- assumption boundary: `BOUNDED_ADAPTED_PROCESS_PREDICTABLE_CENTER_NO_IID_REQUIRED`;
- predictor: `BETA_HALF_SMOOTHED_PREVISIBLE_MEAN_V1`;
- analysis order: `TASK_ID_ASC_THEN_REPLICATE_ASC`;
- author implementation reference: `gostevehoward/confseq@5ffe733ca2447a2e28c2c91f3b00086173f2ab2c`;
- frozen boundary parameter digest: `4deabb17370edfc770b7612235ee9dfddf932dfc21e894161fb2757ea45a1329`;
- frozen `zeta(1.4)` binary64 hex: `0x1.8d8292bd8c3a6p+1`.

The boundary-parameter digest is part of the boundary-method string imported by `ProductStatisticalPlan`; therefore a numeric theorem-runtime change changes the plan digest even if every high-level experimental count remains unchanged.

P9 support for each canonical workload family requires both:

1. exact realized finite-panel Pareto/noninferiority inequalities against every B0-B3 baseline;
2. time-uniform average-conditional-mean lower-bound support at the frozen multiplicity level.

Neither component can rescue failure of the other.

## Generalization family

G1-G5 are a separate preregistered family of `5*4*3=60` claims. The generalization familywise error is `0.05`, giving a two-sided per-claim error `0.05/60`; the underlying Theorem-4 crossing probability is half of that value.

Every G-axis is a separately frozen finite shift panel. `GENERALIZATION_SUPPORTED` means the five preregistered shift panels satisfy the exact + anytime-valid gates. It does not imply universal generalization.

## Task partition and leakage control

Task identities are partitioned deterministically before outcomes into calibration, primary confirmatory and G1 holdout populations. B2 may fit only calibration tasks and must explicitly forbid both downstream task sets.

G2-G5 use separately frozen materialized source/model/economics/perturbation identities and forbid policy retuning.

## Repeated-trial planning

The existing cluster-aware variance decomposition

`Var(mean) ~= sigma_between^2/N_tasks + sigma_within^2/(N_tasks*R)`

is retained solely as a calibration-derived resource-planning diagnostic. It is not the V5.1 confidence-sequence theorem and must never be reported as a confirmatory power guarantee.

The final V5.1 gate recomputes its confidence sequence from the actually observed bounded sequence. If the achieved evidence is insufficient, the gate fails; the protocol is not retuned after outcomes.

## Coverage and execution completeness

The primary raw population is the exact frozen `task × policy × replicate` product. Every P9 baseline comparison must reconstruct the same task/replicate population and `coverage=1.0`; any missing or extra unit prevents certification before statistical inequalities are considered.

## Product aggregation

A single family cannot establish global qualification. Product qualification requires P19 roots for exactly the two canonical source-registry families under identical repository and methodology identities, plus the remaining fault-tolerance and independently attested replication obligations.
