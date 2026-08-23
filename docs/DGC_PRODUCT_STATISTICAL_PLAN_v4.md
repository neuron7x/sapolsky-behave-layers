# DGC Product Statistical Plan v4

Status: `FROZEN_PRE_EXECUTION_STATISTICAL_PLAN_V4`
Date: 2026-08-23
External confirmatory outcomes observed: **NO**

V4 supersedes V3 for future product-evidence execution. V3 remains preserved and reviewable. V4 changes the primary inferential theorem before external outcomes; it does not change the frozen business claim boundary or manufacture evidence.

## Workload and policy panel

Primary external workload families remain:

1. SWE-bench Verified;
2. Terminal-Bench 2.1.

Policy arms remain exactly B0, B1, B2, B3 and DGC under one controlled-comparison frame.

## Task populations

The deterministic three-way partition remains:

- calibration: 20%;
- primary confirmatory: 60%;
- G1 unseen-task holdout: 20%.

The three sets are frozen before outcomes, disjoint and complete. B2 may use only calibration tasks. Primary P9 may use only primary-confirmatory tasks. G1 may use only G1 holdout tasks.

## Endpoints

For each baseline and paired `(task, replicate)` cell:

- cost gain: `baseline_total_operational_cost - DGC_total_operational_cost`;
- quality gain: `DGC_quality - baseline_quality`;
- catastrophic-regret gain: `baseline_regret - DGC_regret`.

Operational cost must use the complete physical cost boundary; coordinator metering alone is not cost evidence.

## Error budget

Global P9 familywise alpha: `0.05`.

Primary multiplicity:

`2 families × 4 baselines × 3 endpoints = 24 claims`.

Per-claim alpha:

`0.05 / 24 = 0.0020833333333333333`.

G1-G5 multiplicity is a separate preregistered family:

`5 axes × 4 baselines × 3 endpoints = 60 claims`,

with per-claim alpha

`0.05 / 60 = 0.0008333333333333334`.

Bonferroni/union-bound control is used so cross-endpoint or cross-baseline independence is not required.

## Noninferiority margins

Frozen primary margins remain:

- quality: `0.02`;
- catastrophic regret: `0.01`.

Minimum cost effect of interest `0.05` remains a **resource-planning target**, not the scientific success threshold. Scientific cost success requires a strictly positive lower confidence bound.

## Exact finite-panel fact

For every B0-B3 baseline, the complete observed frozen panel must satisfy:

- mean cost gain `> 0`;
- mean quality gain `>= -0.02`;
- mean catastrophic-regret gain `>= -0.01`;
- full matched coverage.

This is a deterministic panel statement and carries no probability claim.

## Primary inference: anytime-valid average conditional mean

V4 replaces the V3 cross-pair-independence-dependent empirical-Bernstein promotion theorem with a time-uniform nonparametric empirical-Bernstein confidence sequence for the **average conditional mean** of the precommitted bounded observation sequence.

Primary implementation authority:

`cwc/governance/average_conditional_mean_cs.py`

Theorem authority:

Howard, Ramdas, McAuliffe, Sekhon (2021), Annals of Statistics, DOI `10.1214/20-AOS1991`.

Analysis order is frozen outcome-independently as:

`TASK_ID_ASC_THEN_REPLICATE_ASC`.

Primary inferential success for every family/baseline requires:

- cost lower bound `> 0`;
- quality lower bound `>= -0.02`;
- catastrophic-regret lower bound `>= -0.01`.

The primary theorem does not require iid observations or independent provider requests. It targets the average conditional mean of the adapted bounded sequence.

## Legacy sensitivity inference

Maurer-Pontil fixed-time empirical-Bernstein calculations over the paired micro-sequence remain recorded as sensitivity evidence. Their result is explicitly labeled conditional on cross-pair independence and cannot override the V4 primary authority.

## Repetitions and sizing

Repeated trials remain mandatory because they characterize execution variability and improve information in the sequential bounded process. The hard range remains:

- minimum: 5 trials/task;
- maximum: 50 trials/task.

Cluster-aware variance sizing and finite-panel Bernstein proxy sizing remain **planning-only**. Neither is the final confirmatory theorem.

Target planning power remains `0.90`; if calibration-based planning predicts the hard cap cannot reach the desired precision, the generation is `UNDERPOWERED` and must not weaken thresholds post hoc.

## CCF, G1-G5 and replication

P9 also requires complete CCF headroom audit. After primary P9, all five preregistered G1-G5 axes must pass the same exact + anytime-valid inferential structure with no policy retuning.

Independent replication requires fresh external execution subjects, method identity and signed external attestation; self-replay cannot satisfy replication.

## Promotion rule

A product-evidence stage may advance only from replayable raw evidence and recomputed authorities. No boolean declaration, favorable point estimate, synthetic trace or planning calculation may substitute for the required external observation.

`PRODUCT_QUALIFIED=false` until the full chain is actually observed.
