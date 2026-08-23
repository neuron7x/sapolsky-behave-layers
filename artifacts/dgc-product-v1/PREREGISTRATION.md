# DGC Product v1 — Current Pre-execution Registration

Status: `FROZEN_PRE_EXECUTION_PROTOCOL_V3 / EXTERNAL_CONFIRMATORY_OUTCOMES_UNOBSERVED`
Protocol generation: `DGC_PRODUCT_PAIRED_CLUSTER_AWARE_V3_WITH_G1_HOLDOUT`
Date frozen: 2026-08-23

The previous preregistration generation is preserved at `PREREGISTRATION_V1_ARCHIVE.md`. This V3 generation was frozen before external confirmatory outcomes and supersedes V1 for future product-evidence execution.

Primary claim authority: `docs/DGC_PRODUCT_CLAIM_v1.md`.
Current statistical-plan authority: `docs/DGC_PRODUCT_STATISTICAL_PLAN_v3.md`.
Mathematical authority: `docs/DGC_STATISTICAL_AUTHORITY_V3.md`.
External source identities: `docs/DGC_EXTERNAL_WORKLOAD_PANEL_v1.md` and `external_workload_sources.json`.

The primary confirmatory experiment MUST NOT execute until all of the following are frozen and hash-bound:

1. external workload bytes are materialized, semantically reverified and promoted to `MATERIALIZED_VERIFIED`;
2. model/prompt/tool/environment/budget/pricing/scorer/governance execution manifests are content-addressed;
3. CCF quantizer/oracle semantics are frozen;
4. deterministic three-way task partition is sealed: calibration / primary confirmatory / G1 unseen-task holdout;
5. exact G1-G5 evaluation manifests and policy-role mapping are frozen with no retuning;
6. B2 is fitted only from calibration tasks, with primary-confirmatory and G1 tasks forbidden;
7. final executable B0-B3+DGC harness is frozen;
8. repeated-trial count is frozen from calibration-only planning evidence under the hard resource cap;
9. paired-randomness protocol and cross-pair independence assumption are frozen;
10. primary confirmatory and G1-G5 outcome bytes remain unseen before all preceding authorities are sealed.

Primary scientific support requires both:

- exact frozen-panel Pareto/noninferiority success;
- empirical-Bernstein lower-bound support under the frozen cross-pair independence assumption;

plus complete physical-cost accounting, CCF audit, multiplicity correctness and raw-subject replay.

G1-G5 scientific support requires the same exact + bounded-inference conjunction on every preregistered axis.

The V3 protocol explicitly distinguishes deterministic facts about executed panels from conditional probabilistic inference. A favorable point estimate cannot substitute for a failed confidence bound, and a confidence bound cannot rescue an unfavorable exact panel.

Any change after external confirmatory outcome inspection creates a new preregistration generation. No existing generation may be silently rewritten after outcome inspection.

This preregistration does not authorize a real-workload claim, independent-replication claim, product qualification or production control.
