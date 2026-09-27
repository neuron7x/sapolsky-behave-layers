# DGC Product v1 — Current Pre-execution Registration

Status: `FROZEN_PRE_EXECUTION_PROTOCOL_V5_1 / EXTERNAL_CONFIRMATORY_OUTCOMES_UNOBSERVED`
Protocol generation: `DGC_PRODUCT_ANYTIME_VALID_ACM_V5_1_BINARY64_PARAMETER_BOUND`
Date frozen: 2026-08-24

Historical preregistration generations V1, V3, V4 and pre-binary64 V5 are preserved as immutable archives. V5.1 is a pre-outcome theorem-runtime identity correction. No external confirmatory outcome bytes were inspected before this correction.

## Why V5.1 exists

V5 correctly replaced the anti-conservative V4 shortcut with the authors' exact Eq. (10) polynomial-stitching formula. A subsequent exact-runtime audit found that the decimal hardcode used for `zeta(1.4)` was one binary64 ULP above the value produced by the pinned `confseq` Boost reference path. That old value was slightly more conservative, but it was not an exact binary64 replay of the reference implementation.

V5.1 therefore freezes the complete numeric boundary identity before any outcome-bearing execution:

- `eta = 2.0`;
- `s = 1.4`;
- `v_min = 1.0`;
- default rescaled support parameter `c = 1.0`;
- `zeta(1.4)` binary64 hex = `0x1.8d8292bd8c3a6p+1`;
- canonical boundary-parameter SHA-256 = `4deabb17370edfc770b7612235ee9dfddf932dfc21e894161fb2757ea45a1329`.

The boundary method identity embeds the first 16 hex characters of this parameter digest, so changing any frozen numeric parameter changes the executable statistical-plan digest through the imported boundary identity.

Primary claim authority: `docs/DGC_PRODUCT_CLAIM_v1.md`.
Current statistical-plan authority: `docs/DGC_PRODUCT_STATISTICAL_PLAN_v5.md`.
Current mathematical authority: `docs/DGC_STATISTICAL_AUTHORITY_v5.md`.
Theorem audit: `docs/DGC_THEOREM_AUDIT_v5.md`.
External source identities: `docs/DGC_EXTERNAL_WORKLOAD_PANEL_v1.md` and `external_workload_sources.json`.

## Frozen primary inference identity

- inference: `HOWARD_RAMDAS_MCAULIFFE_SEKHON_THEOREM4_POLY_STITCHING_EXACT_V3`;
- boundary: `HOWARD_EQ10_POLYNOMIAL_STITCHING_EXACT_V2_4deabb17370edfc7`;
- estimand: `AVERAGE_CONDITIONAL_MEAN_OF_PRECOMMITTED_BOUNDED_SEQUENCE`;
- assumption boundary: `BOUNDED_ADAPTED_PROCESS_PREDICTABLE_CENTER_NO_IID_REQUIRED`;
- predictor: `BETA_HALF_SMOOTHED_PREVISIBLE_MEAN_V1`;
- analysis order: `TASK_ID_ASC_THEN_REPLICATE_ASC`;
- author reference implementation commit: `5ffe733ca2447a2e28c2c91f3b00086173f2ab2c`;
- boundary-parameter digest: `4deabb17370edfc770b7612235ee9dfddf932dfc21e894161fb2757ea45a1329`.

For a desired two-sided per-claim error `delta`, the underlying uniform-boundary crossing probability is frozen as `delta/2`, matching Theorem 4's `1-2*alpha_boundary` statement.

## Pre-execution obligations

The primary confirmatory experiment MUST NOT execute until all of the following are frozen and hash-bound:

1. both canonical external workload families are materialized and semantically reverified;
2. model/prompt/tool/environment/budget/pricing/scorer/governance execution manifests are content-addressed;
3. CCF quantizer/oracle semantics are frozen;
4. deterministic calibration / primary-confirmatory / G1 holdout partition is sealed;
5. exact G1-G5 definitions and semantic B0/B1/B2/B3/DGC role mapping are frozen with no retuning;
6. the fault-injection matrix is frozen before outcome-bearing calibration;
7. B2 is fitted only from calibration tasks, with confirmatory and G1 tasks forbidden;
8. final executable B0-B3+DGC harness is frozen;
9. repeated-trial count is frozen from calibration-only planning evidence under hard resource caps;
10. primary analysis order, theorem identity and boundary-parameter identity are frozen in the executable statistical-plan digest;
11. primary confirmatory, G1-G5 and fault-support outcome bytes remain unseen before all preceding authorities are sealed.

## Scientific support semantics

For each canonical workload family, `P9_SUPPORTED` requires all of:

- exact complete-panel cost superiority plus quality/regret noninferiority against B0-B3;
- V5.1 anytime-valid average-conditional-mean confidence-sequence support using the exact polynomial-stitching boundary and frozen binary64 parameter identity;
- complete ten-component physical-cost accounting;
- complete CCF headroom audit;
- exact multiplicity allocation;
- raw-subject replay reproducing every authority digest.

G1-G5 requires the same exact + V5.1 anytime-valid conjunction on each preregistered shift axis, with no policy retuning. Fault tolerance is a separate replayable proof obligation. Independent replication requires fresh raw execution/cost/CCF subjects under the same frozen methodology plus a verified external signature attestation.

One family P19 root cannot authorize global product qualification. Global qualification requires distinct P19 roots for exactly `SWE_BENCH_VERIFIED` and `TERMINAL_BENCH_2_1`, under the same repository and methodology identities.

The protocol does not claim universal superiority, iid population inference, social-independence proof, production control or customer validation.

Any protocol change after external confirmatory outcome inspection requires a new preregistration generation. Existing generations may never be silently rewritten.
