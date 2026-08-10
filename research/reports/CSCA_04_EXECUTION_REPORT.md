# CSCA-04-SA — Structural World-Model Adequacy Qualification

**Date:** 2026-08-10  
**Authority:** RESEARCH_ONLY  
**Verdict:** `STRUCTURAL_ADEQUACY_SYNTHETIC_QUALIFIED`  
**Shadow inference qualification:** NO

## Executive result

The estimator bottleneck identified by CSCA-03R was not attacked with more Monte-Carlo compute. CSCA-04 tests the next term directly: structural counterfactual model error. The primary mechanism is an intervention-noise-calibrated discrepancy between empirical `do(X)` effects and model-predicted intervention effects. Internal graph sensitivity and observational fit remain diagnostics only.

## P1 — analytic identifiability attack

A constructive `C=A` support counterexample gives two models, `Y=A` and `Y=C`, with identical factual predictions but different intervention responses. Therefore factual RMSE, observational likelihood, and observational model agreement cannot by themselves certify counterfactual structure. GSS measures model reliance, not causal correctness.

## P2 — operational interventional discrepancy

For split empirical intervention-effect estimates `d1,d2`, `d=(d1+d2)/2`, and model effect `m`:

`IDR = mean((d-m)^2) / [0.25 * mean((d1-d2)^2)]`.

The denominator is an empirical measurement-noise floor. The ratio has no universal cutoff; thresholds are prospectively calibrated.

The first implementation used separate noisy denominators per cell and was corrected before frozen calibration because low-count cells could generate near-zero random denominators. The correction and development-only seed are preserved in `PRE_CALIBRATION_AMENDMENT_001.md`.

## P3 — intervention allocation

Primary allocation was frozen as balanced candidate×context coverage because a shared wrong model class can have low ensemble disagreement.

Post-confirmatory, fresh diagnostic seeds showed at matched total probe count:

- BALANCED: 100% full 8-cell coverage; 100% bad-family flag; 100% good-family pass in the 40-case diagnostic;
- DISAGREEMENT_ONLY: 10% full coverage and 59.375% bad-family flag;
- CREDIT_PRIORITY: 0% full coverage and 87.5% bad-family flag;
- COVERAGE_PLUS_DISAGREEMENT: full coverage but median minimum support only 2/cell and 87.5% good-family pass.

This is diagnostic-only but demonstrates why disagreement is not sufficient as an intervention scheduler when the whole ensemble shares a wrong edge.

## P4 — prospective calibration

Calibration used 64 seeds × 4 known-adequate SCM families = 256 cases. Five budgets were evaluated. The frozen primary budget is 16 probes per candidate×context cell.

Frozen primary thresholds:

- `max_cell_idr <= 4.264566468014008`;
- context standardized-difference threshold `3.2496168935684526`;
- 8/8 candidate×context cells required;
- 16 probes/cell required;
- empirical leverage floor `0.10`.

Calibration was committed before PRIMARY execution.

## P5 — held-out misspecification matrix

PRIMARY: 64 fresh seeds × 10 held-out families = 640 cases.

- structural-misspecification sensitivity: `1.0000` (512/512 inadequate cases; Wilson 95% lower bound ≈0.99255);
- known-adequate specificity: `0.9921875` (127/128; Wilson 95% interval ≈[0.95707, 0.99862]);
- zero-cause global authority: `0`;
- collinear identifiability family accepted: `0/64`;
- median factual RMSE in that rejected collinear family: `0.150751`.

Independent replication: another 64 seeds × 10 families = 640 cases.

- sensitivity: `1.0000` (512/512; Wilson lower ≈0.99255);
- specificity: `1.0000` (128/128; Wilson lower ≈0.97086);
- zero-cause global authority: `0`;
- collinear identifiability accepted: `0/64`;
- median factual RMSE: `0.152518`.

Thus low factual error did not rescue interventionally wrong structure.

## P6 — context and GSS attack

Context scope:

- PRIMARY M9 sign-flip: 64/64 `CONTEXT_CONDITIONAL_ONLY`, 0 global-direction acceptance;
- REPLICATION M9: 64/64 context-conditional, 0 global acceptance;
- M8 cause-switch: 63/64 context-conditional + 1 conservative structural abstention in PRIMARY; 64/64 context-conditional in replication.

GSS diagnostic on fresh seeds:

- correct C0: factual GSS top=true cause 16/16;
- shared-wrong-edge M1: factual GSS top=`C` 16/16 even though `C` is spurious; IDR rejected 16/16;
- collinear M10: factual GSS top=true cause only 10/16; IDR rejected 16/16.

Therefore GSS is retained as a fragility/reliance diagnostic and rejected as independent causal authority.

## P7 — authority envelope

A production-isolated `StructuralAdequacyEnvelope` and fail-closed `StructuralAuthorityPolicy` were implemented. The possible states are:

- `STRUCTURAL_ADEQUACY_ACCEPTED_SYNTHETIC`;
- `CONTEXT_CONDITIONAL_ONLY`;
- `ABSTAIN_STRUCTURAL_MISSPECIFICATION`;
- `ABSTAIN_INSUFFICIENT_STRUCTURAL_COVERAGE`;
- `FALSIFIED_NO_CAUSAL_LEVERAGE`.

This module is **not** wired into token generation or existing shadow inference. Synthetic structural qualification does not supersede the negative ACT-R&D-03 result by itself.

## Secondary sample-efficiency diagnostic

On 80 fresh diagnostic cases, budget-specific calibration thresholds yielded 1.0 sensitivity and 1.0 specificity at 2/4/8/16/32 probes per cell. This is too small and post-confirmatory to reduce the frozen 16/cell primary budget; it only motivates a future prospective sparse-intervention study.

## Scientific boundary

Supported narrowly: explicit interventions can expose the controlled structural errors that factual fit, ensemble agreement and estimator precision failed to detect; context-varying mechanisms can be scoped to context rather than globally authorized.

Not supported: causal adequacy of a real language-model world model, semantic real-world causality, biological causality, shadow-inference qualification, replay-control utility, physical-compute advantage, or active causal control.


## Verification

- `CSCA04-GATE`: PASS.
- `CSCA03R-GATE`: PASS.
- `RD03-GATE`: PASS while preserving the negative uncertainty verdict.
- research-ops / research-execution / research-ingestion: PASS.
- architecture / hermeticity / complexity / inference-integrity: PASS.
- doc gate: 54 claims / 54 hypotheses / 0 orphans.
- verdict binding: 52 sealed claims + 2 NOT_TESTED unbound by design.
- new CSCA-04 unit/gate tests: 4 PASS.
- post-binding selected regression set (structural + verdict + inference-integrity): 33 PASS.
- full test collection: 398 tests collected, 0 collection errors.
- a complete behavioral `pytest -q` run exceeded the available 240 s execution window before completion; no full-suite PASS is claimed.

## Next hard gate

`CSCA-05 — Composed Causal Authority & Real-Model Intervention Shadow Pilot`.

It must combine:

1. structural interventional adequacy;
2. context-conditional scope;
3. finite-budget CRN/antithetic credit envelope;
4. uncertainty/abstention;
5. immutable real-model intervention traces;
6. noninterference with base generation.

Until that prospective composition passes, shadow inference remains unqualified.
