# CWC-FLAGSHIP-ROUTE-02 — Preregistration

Date frozen: 2026-08-11
Status: PRE-IMPLEMENTATION / NO R2 MODEL OUTPUTS OBSERVED
Parent negative: `CWC-FLAGSHIP-ROUTE-01_NOT_SUPPORTED`

## Purpose

R1 established that a single CALIBRATION-seed ridge in raw block-1 hidden coordinates does not
transfer robustly across independently trained model seeds. A post-hoc, non-rescuing diagnostic
showed that fitting the same ridge form on each model's own CALIBRATION representation improved
cell PASS from 2/12 to 6/12, so cross-seed coordinate nonalignment is a concrete candidate failure
mechanism. R2 gives this mechanism exactly one confirmatory rescue attempt. There is no R3 rescue
under this programme decision.

## Frozen question

For independently trained two-exit byte-level Transformers, does a **per-model CALIBRATION-only**
decision-relevant ridge router convert second-block marginal-value heterogeneity into a strict
quality advantage over the fixed depth Pareto envelope and matched generic controls on both frozen
real-data families, across every fresh PRIMARY seed and again under fresh REPLICATION seeds?

## Model and training contract

Unchanged from CWC-FLAGSHIP-ROUTE-01 except seeds and experiment namespace:

- byte vocabulary 256;
- sequence length 64;
- d_model 64;
- 4 attention heads;
- 2 independently parameterized Transformer blocks;
- one shared LM head;
- 400 AdamW training steps, batch 16, lr 3e-3, weight decay 0.01;
- dual-exit training loss = 0.5 * (CE_exit1 + CE_exit2);
- training alternates PROSE/CODE exactly as R1.

Fresh model seeds:

- PRIMARY: 74401, 74402, 74403;
- REPLICATION: 74501, 74502, 74503.

No model seed may be changed or replaced after execution begins.

## Data contract and anti-reuse rule

The checksum-bound R1 corpus files remain the source substrate. Cohort file partition remains:

- CALIBRATION: eval1 + eval2;
- PRIMARY: eval3 + eval4;
- REPLICATION: eval5.

R2 window membership uses namespace `CWC-FLAGSHIP-ROUTE-02` and MUST explicitly exclude every
(file_sha256, offset) pair used by R1 in the corresponding family/cohort. Collision resolution is
deterministic and independent of any model output. R2 PRIMARY/REPLICATION case membership is frozen
by source bytes + namespace + cohort + family + file hash + window index before model evaluation.

Windows per file remain 64. Any inability to construct the full non-overlapping cohort is
`NOT_EXECUTABLE`, never a reduced sample.

## Information boundary

At route time the policy observes exactly the R1 amendment-001 representation:

`z = concat(mean_t(h1[t,:]), family_indicator)`

No target, loss, exit-2 state, file identity, case hash or cohort identity is allowed.

## Only allowed mechanism change

Unlike R1, **each evaluated model seed receives its own router calibration** from that model's
CALIBRATION windows. No shared cross-seed ridge exists.

For a given model seed, CALIBRATION fits with fixed alpha=1e-3:

- DECISION_RELEVANT ridge target: `loss_depth1 - loss_depth2`;
- DIFFICULTY_MATCHED ridge target: `loss_depth1`.

Feature standardization, intercept handling and solver are identical to R1. No hyperparameter,
feature, threshold or model search is allowed.

The family-specific frontier slope is also estimated from that same model seed's CALIBRATION rows:

`max(0, (mean_L1 - mean_L2)/(C2-C1))`.

Candidate continues iff predicted marginal gain > frozen per-model family slope * block2_FLOPs.

## Exact resource accounting

Identical to R1 amendment-001/002. Logical FLOPs, 1 MAC = 2 FLOPs. Every dynamic policy pays the
same route envelope. Fixed frontier is the best depth1/depth2 mixture using compute <= candidate
budget. Candidate outside [C1,C2] fails.

## Required baselines

For the exact candidate continuation count in every seed/family cell:

1. FIXED_DEPTH_1;
2. FIXED_DEPTH_2;
3. FIXED_FRONTIER;
4. RANDOM_MATCHED;
5. HIDDEN_NORM_MATCHED;
6. DIFFICULTY_MATCHED (per-model CALIBRATION-only ridge, same sensor/solver);
7. ORACLE_MATCHED (diagnostic sanity only);
8. DECISION_RELEVANT.

## Frozen cell endpoints

Every PRIMARY and REPLICATION seed/family cell must satisfy all:

1. candidate compute within fixed frontier;
2. candidate CE strictly lower than FIXED_FRONTIER at candidate logical FLOPs;
3. candidate CE strictly lower than RANDOM_MATCHED;
4. candidate CE <= HIDDEN_NORM_MATCHED;
5. candidate CE strictly lower than DIFFICULTY_MATCHED;
6. ORACLE_MATCHED CE <= candidate CE;
7. exact matched continuation counts;
8. zero information-boundary violations;
9. all corpus SHA-256 values match;
10. R2 evaluation windows do not overlap R1 windows in the same family/cohort.

Cohort PASS requires every one of six cells PASS and strictly positive median fixed-frontier
advantage in both families. REPLICATION can invalidate PRIMARY success and can never rescue PRIMARY
failure.

## Programme kill rule

- `CWC_FLAGSHIP_ROUTE_02_SUPPORTED_NARROW` iff PRIMARY and REPLICATION both pass fully.
- Any PRIMARY cell failure => `CWC_FLAGSHIP_ROUTE_02_NOT_SUPPORTED`.
- If R2 is NOT_SUPPORTED, the current two-exit learned adaptive-depth subprogramme is **closed**.
  No R3 router rescue, feature search, threshold search or workload substitution is permitted under
  this programme branch. Future adaptive-compute work would require a materially different
  architecture and a new hypothesis lineage, not a repair of this branch.

Even an R2 PASS would not establish external L7/MoD/MoE superiority or independent replication.
