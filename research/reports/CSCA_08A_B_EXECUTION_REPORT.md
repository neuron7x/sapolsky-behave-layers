# CSCA-08A/B — Assumption-Typed Regime Identifiability Execution Report

**Verdict:** `OBSERVATIONAL_IDENTIFYING_CONTRACT_QUALIFIED_SYNTHETIC_NARROWED`  
**Authority:** `CAUSAL_CANDIDATE_UNDER_EXPLICIT_ASSUMPTIONS_ONLY`

## Provenance

Exploratory pilot used only seeds 1000..1063. Confirmatory implementation and all pass predicates were frozen at commit `3edbb2a`, then a pre-data import-path repair was committed at `af68416`. The first attempted authoritative command failed at import before generating/reading cohort data; no threshold, seed or scientific predicate changed. The authoritative cohorts then used PRIMARY 50000..50127 and REPLICATION 60000..60127.

## Confirmatory results

Each family: 128 seeds/cohort, 4096 rows/seed before selection.

PRIMARY:
- V0 valid: candidate 128/128; median absolute beta error 0.01219; zero unconditional authority.
- V1 non-proportional direct regime effect: assumption violation 128/128.
- V2 regime-latent confounding: assumption violation 128/128.
- V3 high aleatoric noise: candidate 128/128; median absolute beta error 0.03237.
- V4 selection bias: assumption violation 128/128.
- V5 weak relevance: insufficient-information abstention 128/128.
- V6 coordinated exclusion violation: candidate-under-assumptions 128/128, median error against true beta 0.50064, zero unconditional authority, exclusion debt retained 128/128.
- V7 25% symmetric regime-label corruption: candidate 128/128; measurement-reliability debt retained 128/128.

REPLICATION:
- V0 128/128 candidate; median error 0.01202.
- V1/V2/V4 128/128 assumption violation each.
- V3 128/128 candidate; median error 0.03251.
- V5 128/128 insufficient-information abstention.
- V6 128/128 candidate-under-assumptions; median error 0.50078; zero authority; exclusion debt 128/128.
- V7 126/128 candidate and 2/128 conservative violations; zero authority; measurement debt 128/128.

Exact coordinated-exclusion construction: beta 0.8 vs observationally equivalent reparameterized beta 1.3; X/W path error 0, Y path error `1.7763568394002505e-15`.

Runtime for both cohorts in the current CPU container: about 1.33 s inside the experiment, 1.98 s process wall time, peak RSS about 114108 KB. These are local telemetry only.

## Interpretation

The positive is deliberately narrow. Heterogeneous observed regimes can recover the correct linear-effect candidate when the IV-style contract is true, and the implemented witnesses detect the tested non-proportional direct effects, regime-confounding and selection violations while not confusing high aleatoric noise with structural failure. But V6 proves that all observable checks can survive while the causal coefficient is wrong by 0.5. The new runtime primitive is therefore assumption-carrying inference, not passive causal truth.

## Non-promotion

No semantic causality, real-trace exogeneity, replay control, active control, or architecture promotion follows. The next hard work is to make assumption debt first-class in memory/planning and to choose evidence acquisitions by certified information gain per cost.
