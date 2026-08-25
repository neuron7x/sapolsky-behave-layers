# DGC Product v1 — Current Pre-execution Registration

Status: `FROZEN_PRE_EXECUTION_PROTOCOL_V4 / EXTERNAL_CONFIRMATORY_OUTCOMES_UNOBSERVED`
Protocol generation: `DGC_PRODUCT_ANYTIME_VALID_ACM_V4_WITH_G1_HOLDOUT`
Date frozen: 2026-08-23

V1 and V3 preregistration generations are preserved as immutable archives. V4 was frozen before external confirmatory outcomes and supersedes V3 for future product-evidence execution.

Primary claim authority: `docs/DGC_PRODUCT_CLAIM_v1.md`.
Current statistical-plan authority: `docs/DGC_PRODUCT_STATISTICAL_PLAN_v4.md`.
Current mathematical authority: `docs/DGC_STATISTICAL_AUTHORITY_V4.md`.
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
9. primary analysis sequence is outcome-independently frozen as `TASK_ID_ASC_THEN_REPLICATE_ASC`;
10. primary confirmatory and G1-G5 outcome bytes remain unseen before all preceding authorities are sealed.

Primary P9 scientific support requires all of:

- exact frozen-panel Pareto/noninferiority success;
- anytime-valid nonparametric average-conditional-mean confidence-sequence support;
- complete ten-component physical-cost accounting;
- complete CCF headroom audit;
- exact multiplicity allocation;
- raw-subject replay reproducing the declared authorities.

The V4 primary inference does **not** require iid observations or independent provider requests. It targets the average conditional mean of the precommitted bounded adapted sequence. The previous independence-sensitive Maurer-Pontil micro-level calculation is retained only as sensitivity evidence and cannot authorize promotion.

G1-G5 scientific support requires the same exact + anytime-valid conjunction on every preregistered axis, with no policy retuning.

The protocol distinguishes:

1. deterministic facts about the complete executed finite panels;
2. time-uniform probabilistic statements about average conditional effects;
3. shift-panel evidence across G1-G5;
4. independently attested fresh replication;
5. product/production qualification.

None may be substituted for another.

Any change after external confirmatory outcome inspection creates a new preregistration generation. No existing generation may be silently rewritten after outcome inspection.

This preregistration does not authorize a real-workload claim, independent-replication claim, product qualification or production control.
