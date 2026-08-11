# CSCA-08A/B — Final Verification Record

**Date:** 2026-08-11  
**Scientific verdict:** `OBSERVATIONAL_IDENTIFYING_CONTRACT_QUALIFIED_SYNTHETIC_NARROWED`  
**Maximum authority:** `CAUSAL_CANDIDATE_UNDER_EXPLICIT_ASSUMPTIONS_ONLY`

## What qualified

- machine-readable assumption types distinguish empirically falsifiable, partially falsifiable, provenance-required and factual-channel-untestable assumptions;
- two-regime IV-style moments recover the hidden-confounded homogeneous linear effect in the frozen synthetic valid family;
- negative-control and over-identification witnesses reject the frozen tested regime-confounding, non-proportional direct-effect and selection-bias violations;
- high aleatoric noise is not automatically relabeled structural failure;
- weak regime relevance produces `INSUFFICIENT_INFORMATION_BUDGET`;
- coordinated exclusion survives observable diagnostics only as `CAUSAL_CANDIDATE_UNDER_ASSUMPTIONS`, with explicit exclusion debt and zero unconditional authority;
- a generic maximin certified KL-information-per-cost acquisition kernel is implemented; it vetoes compute when any unresolved alternative has zero certified information rate.

## What did not qualify

- proof of exclusion or full exogeneity from passive moments;
- regime-label reliability from the moments themselves;
- real nanochat/prose/code regime validity;
- semantic causal authority;
- replay control;
- active control;
- architecture/Pareto promotion.

## Confirmatory numbers

Both PRIMARY and independent REPLICATION used 128 fresh seeds/family, 4096 generated rows/seed before selection.

- V0 valid: 128/128 candidate in each cohort; median absolute beta error 0.01219 / 0.01202.
- V1 non-proportional direct effect: 128/128 assumption violation in each cohort.
- V2 regime-latent confounding: 128/128 assumption violation in each cohort.
- V3 high aleatoric noise: 128/128 candidate; median error 0.03237 / 0.03251.
- V4 selection bias: 128/128 assumption violation in each cohort.
- V5 weak relevance: 128/128 insufficient-information abstention in each cohort.
- V6 coordinated exclusion: 128/128 candidate-under-assumptions; median error versus true beta 0.50064 / 0.50078; authority count 0; exclusion-debt rate 1.0.
- V7 symmetric regime-label corruption: 128/128 candidate PRIMARY, 126/128 candidate REPLICATION; authority count 0; measurement-debt rate 1.0.

Exact V6 construction: beta 0.8 vs reparameterized 1.3; max X-path error 0, W-path error 0, Y-path error `1.7763568394002505e-15`.

## Verification

PASS:
- `scripts/csca08_gate.py --self-test`: 5/5 semantic/authority mutations killed;
- `scripts/csca08_gate.py`;
- CSCA-07 parent gate;
- research-ops / research-execution / research-ingestion;
- causal-debt / VIA / architecture / hermeticity / complexity / inference-integrity;
- documentation and verdict-binding gates;
- evidence validation;
- new CSCA-08 + information-governor tests: 12 PASS;
- all `tests/test_csca*.py`: 19 PASS;
- full repository collection: 426 tests, zero collection errors;
- new Python modules/scripts compile;
- `git diff --check` PASS.

Not claimed:
- full behavioral repository pytest PASS was not executed to completion in this iteration;
- independent third-party/operator replication;
- real-hardware GPU/energy qualification.

## Next scientific boundary

The next load-bearing cognitive primitive is not another estimator. It is autonomous countermodel search plus proof-carrying epistemic state: for every surviving causal candidate, generate the cheapest observationally compatible model that changes the causal conclusion, then allocate evidence acquisition by certified information-per-cost. Memory/replay/planning must remain blocked from treating the candidate as causal truth while such a countermodel survives.
