# CSCA-03R — Deterministic Budgeted Counterfactual Credit Qualification

**Date:** 2026-08-10  
**Authority:** RESEARCH_ONLY  
**Final verdict:** `CSCA_03R_COUPLED_ESTIMATOR_QUALIFIED`  
**Shadow inference / replay / architecture promotion:** NOT AUTHORIZED

## 1. Why CSCA-03 was destroyed before accepting its positive result

A reproducibility attack changed only `PYTHONHASHSEED` while keeping the declared experiment/model/estimator seed fixed. The historical independent-resampling comparator consumed RNG draws while iterating a Python `set`, so different hash orders assigned the same RNG draws to different predecessor variables. The comparator therefore produced different credit vectors for the same declared seed.

CSCA-03 was marked `INSTRUMENT_INVALID_LEGACY_COMPARATOR_NONDETERMINISTIC`. Its already executed calibration/PRIMARY artifacts are retained under `artifacts/csca-03-invalid/`; they have no qualification authority.

The only comparator correction was deterministic iteration of the predecessor set (`sorted(coalition)`). Because PRIMARY had already been observed, the repaired code was **not** used to rescue the old experiment. CSCA-03R was preregistered with fresh seed ranges before fresh confirmatory execution.

## 2. Fresh confirmatory design

- calibration: 32 seeds `61000..61031`;
- PRIMARY: 128 fresh seeds `62000..62127`;
- independent replication: 128 fresh seeds `72000..72127`;
- 8 rows/context frozen a priori;
- budgets: 8,16,32,64,128,256 path evaluations;
- four environment families E0/E1/E2/E3;
- exact teacher + deterministic legacy + CRN + antithetic CRN + exploratory double-antithetic.

PRIMARY and replication contain **44,099,584 structural evaluations**. Including calibration, the valid CSCA-03R program contains **49,612,032 structural evaluations**. Including the preserved invalid CSCA-03 calibration+PRIMARY attack, the current repository retains **77,174,272 structural evaluations** across this estimator investigation.

## 3. Determinism gate

The repaired legacy comparator was executed under five distinct `PYTHONHASHSEED` values with identical declared model/data/estimator seed. The resulting credit vector was byte-equivalent after canonical JSON serialization in all five executions. The new CRN estimators do not consume RNG through unordered predecessor sets.

## 4. E0 — structural non-cause cancellation

`CRN_CHAIN_MC` uses the same predecessor intervention assignment on both sides of each marginal contribution. Therefore a variable absent from the structural evaluator cancels algebraically per draw.

Observed confirmatory result:

- false-credit mass on B,C,D = **0** for every CRN PRIMARY and replication unit at all six budgets;
- E0 causal top-set recovery = **1.0** at all six budgets in both cohorts;
- CRN exact-teacher error is lower than deterministic legacy at every budget.

Mean per-row RMSE, budget 8 → 256:

PRIMARY:
- deterministic legacy: `0.63836 → 0.11701`;
- CRN: `0.24951 → 0.04886`.

REPLICATION:
- deterministic legacy: `0.63331 → 0.11598`;
- CRN: `0.24609 → 0.04979`.

## 5. E1 — interaction attack / antithetic estimator

The interaction family prevents the antithetic method from qualifying only because of an additive single-cause symmetry.

Corrected aggregate-MSE ratios `ANTITHETIC_CRN_MC / CRN_CHAIN_MC`:

| budget | PRIMARY | REPLICATION |
|---:|---:|---:|
| 8 | 0.51295 | 0.50832 |
| 16 | 0.51544 | 0.53064 |
| 32 | 0.54010 | 0.55582 |
| 64 | 0.52186 | 0.51831 |
| 128 | 0.52306 | 0.51697 |
| 256 | 0.51702 | 0.51989 |

The preregistered `<=0.90×` condition passed **6/6 budgets** independently in both cohorts.

Post-confirmatory exact rational enumeration of all 8 `(context,A,B)` states × 24 permutations × 16 replacement assignments verifies unbiased CRN/antithetic expectation, exact dummy-player cancellation, and predicts the matched-budget MSE ratio exactly as `192/373 = 0.5147453083`. This analytic check has no claim-upgrade authority; it explains the observed magnitude mechanistically.

## 6. The variance-only P0 gate is falsified

The proposed global diagnostic ceiling was `Var(hat_phi) < 0.0079160524`.

It is **not necessary**: E0 CRN has zero structural-null false credit at every budget while mean maximum component variance remains above the ceiling even at budget 256 (`~0.0156`). Structural cancellation protects null variables despite nonzero uncertainty on the true cause.

It is **not sufficient**: E3 deliberately gives the evaluator a false structural edge `C` with coefficient 0.9. At budgets 64/128/256, antithetic estimator variance is around `1e-34..1e-35`, RMSE to the wrong-model teacher is around `7e-17`, yet false-credit mass relative to the true SCM is **0.9** and RMSE to the true teacher is `0.636396`.

Factual fit can still look good: wrong-vs-true factual RMSE is `0.14882` PRIMARY and `0.19486` replication.

Therefore the dominant decomposition is:

`hat_phi_M - phi_true = estimator_error + structural_model_error`.

More Monte-Carlo compute can drive `estimator_error -> 0` while leaving structural model error untouched. A better estimator can become more precisely wrong.

## 7. Context-conditional authority

For the sign-flip E2 family:

- PRIMARY: `3072/3072 CONTEXT_CONDITIONAL_ONLY`, `0 GLOBAL_DIRECTION_ACCEPT`;
- REPLICATION: `3072/3072 CONTEXT_CONDITIONAL_ONLY`, `0 GLOBAL_DIRECTION_ACCEPT`.

This only verifies behavior when the correct context partition is supplied. It does not solve context discovery.

## 8. Scientific verdict

`CSCA_03R_COUPLED_ESTIMATOR_QUALIFIED` is narrow support for estimator construction under controlled SCMs:

- CRN coupling is the first reproduction-queue estimator retained;
- antithetic CRN is retained as the preferred finite-budget variant for the frozen symmetric baseline;
- deterministic legacy is retained only as a historical comparator;
- `VARIANCE_ONLY_AUTHORITY` is killed;
- Variational Credit Network remains blocked as causal authority.

ACT-R&D-03 remains negative. CSCA-03R does **not** establish that a learned counterfactual world model is causally adequate and therefore does not unlock shadow inference, real-model replay or active causal control.

## 9. Next weakest causal link

The estimator problem is no longer the dominant blocker. The next hard gate is structural-model adequacy:

> Can the system detect `phi_M - phi_true` when factual prediction is good, estimator variance is tiny, and model-family members agree?

The next experiment must make context/structure uncertainty intervention-sensitive rather than prediction-error-sensitive. Until that succeeds, causal credit stays offline/research-only.
