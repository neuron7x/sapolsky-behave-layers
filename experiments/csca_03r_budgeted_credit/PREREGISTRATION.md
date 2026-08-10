# CSCA-03R — Deterministic Budgeted Counterfactual Credit Qualification

**Status:** FROZEN BEFORE COMPARATOR FIX AND FRESH CONFIRMATORY EXECUTION  
**Parent:** CSCA-03 instrument-invalid due hash-order-dependent legacy comparator.  
**Authority:** RESEARCH_ONLY. No shadow inference, replay authority or architecture promotion.

## Purpose

Retest the CSCA-03 mechanism under a hermetic comparator. The only authorized legacy-comparator correction is to iterate predecessor coalition members in deterministic sorted order while preserving the same RNG stream, coalition semantics and estimator definition.

## Frozen cohorts

- CALIBRATION: `61000..61031` (32 seeds), diagnostics only.
- PRIMARY: `62000..62127` (128 fresh seeds).
- INDEPENDENT_REPLICATION: `72000..72127` (128 fresh seeds).
- `rows_per_context = 8` frozen a priori from demonstrated compute feasibility.
- budgets `8,16,32,64,128,256`.
- environments E0/E1/E2/E3 unchanged.

No seed from CSCA-03 may enter CSCA-03R.

## Estimators

- `LEGACY_INDEPENDENT_MC_DETERMINISTIC`: historical independent-resampling semantics with `sorted(coalition)` solely to make RNG-to-variable assignment hermetic.
- `CRN_CHAIN_MC`.
- `ANTITHETIC_CRN_MC`.
- `DOUBLE_ANTITHETIC_CRN_MC` exploratory only.
- exact Shapley teacher.

## Confirmatory predicates

All must pass independently in PRIMARY and REPLICATION:

1. E0 CRN structural-null false-credit mass <= `1e-12` for every unit.
2. E0 CRN aggregate exact-teacher RMSE < deterministic-legacy RMSE at all six budgets.
3. E0 CRN causal top-set recovery = `1.0` at all budgets.
4. E1 CRN false-credit mass on C,D <= `1e-12` for every unit.
5. E1 antithetic aggregate MSE <= `0.90 × CRN MSE` at >=4/6 budgets.
6. E2 `GLOBAL_DIRECTION_ACCEPT = 0`; every tested sign-inversion unit must remain context-conditional or abstain.
7. E3 must reproduce the variance-only-authority counterexample: low estimator variance does not eliminate structural false credit.
8. Determinism test: identical declared seed/config must produce byte-identical estimator credits across at least five distinct `PYTHONHASHSEED` values for the corrected legacy comparator and all new estimators.

PASS: `CSCA_03R_COUPLED_ESTIMATOR_QUALIFIED`.

Any comparator determinism failure: `CSCA_03R_INSTRUMENT_INVALID`.
Any core predicate failure: `CSCA_03R_COUPLED_ESTIMATOR_NOT_QUALIFIED`.

## Boundaries

This experiment qualifies estimator construction only. It cannot repair the ACT-R&D-03 counterfactual-model adequacy failure. A correct estimator of a wrong model remains wrong.
