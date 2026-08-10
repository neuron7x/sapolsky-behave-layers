# CSCA-04-SA — Structural World-Model Adequacy Qualification

**Authority before execution:** RESEARCH_ONLY  
**Primary question:** can sparse, prospectively calibrated interventions detect structural counterfactual error when factual prediction, ensemble agreement, and credit-estimator variance are misleading?

## Seven phases

1. **P1 Analytic identifiability attack.** Establish that observational fit/internal graph sensitivity cannot by themselves certify intervention correctness.
2. **P2 IDR construction.** Compare empirical `do(X)` response against model-predicted intervention response, normalized by an independently estimated intervention measurement-noise floor.
3. **P3 Intervention allocation.** Compare `BALANCED`, `DISAGREEMENT_ONLY`, `CREDIT_PRIORITY`, and `COVERAGE_PLUS_DISAGREEMENT` at matched intervention counts.
4. **P4 Prospective calibration.** Freeze budget-specific structural-adequacy thresholds from calibration families only.
5. **P5 Held-out structural misspecification.** Test spurious edge, missing edge, sign error, coefficient error, latent confounding, zero-cause, higher-order interaction, and collinear non-identifiability.
6. **P6 Context/GSS attack.** Context-varying mechanisms must become context-conditional; Graph Structural Sensitivity is diagnostic-only and must not be treated as correctness evidence.
7. **P7 Authority envelope.** Structural authority may pass only with intervention coverage, calibrated IDR, context scope, independent replication, and frozen thresholds. Shadow inference remains blocked until a real-model interventional pilot.

## Primary diagnostic

For independent split intervention-effect estimates `d1,d2`, let `d=(d1+d2)/2` and model prediction `m`.

`IDR = mean((d-m)^2) / [0.25 * mean((d1-d2)^2)]`.

The denominator estimates the full-sample intervention measurement-noise floor. IDR has no universal cutoff. A budget-specific threshold is frozen as the empirical 99th percentile of the *best-family maximum cell IDR* on calibration-only, interventionally correct SCMs. No confirmatory result may alter it.

## Fail-closed decision

For each held-out case:

- if fewer than 8 candidate×context cells are observed: `ABSTAIN_INSUFFICIENT_STRUCTURAL_COVERAGE`;
- else if best-family max-cell IDR exceeds frozen threshold: `ABSTAIN_STRUCTURAL_MISSPECIFICATION`;
- else if the mechanism changes sign/cause across context: `CONTEXT_CONDITIONAL_ONLY`;
- else: `STRUCTURAL_ADEQUACY_ACCEPTED_SYNTHETIC`.

## Primary qualification conditions

On both PRIMARY and independent replication cohorts:

- specificity on known-adequate held-out context families >= 0.95;
- sensitivity to known-inadequate structural families >= 0.95 under the chosen policy;
- zero false global authority on `M6_ZERO_CAUSE`;
- zero global-direction acceptance on context-sign-flip cases;
- `M10_COLLINEAR_IDENTIFIABILITY` must not be rescued by low factual RMSE;
- thresholds and selected intervention policy frozen before PRIMARY.

No threshold may be changed after confirmatory evaluation. GSS cannot independently authorize causal credit.
