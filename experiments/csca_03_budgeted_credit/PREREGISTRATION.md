# CSCA-03 — Budgeted Counterfactual Credit Estimator Qualification

**Status:** FROZEN BEFORE IMPLEMENTATION/CONFIRMATORY EXECUTION  
**Authority:** RESEARCH_ONLY  
**Parent evidence:** CSCA-01 exact kernel supported narrowly; CSCA-02-UA global uncertainty/abstention not qualified.  
**Promotion authority:** none. This experiment cannot authorize shadow inference or active causal control.

## First-principles problem

The legacy CSCA-01 finite-budget approximation evaluates nested coalitions with fresh random counterfactual assignments at each step. This can inject predecessor-resampling noise into the marginal contribution of the newly added candidate. Before increasing the sample count or training an amortized neural estimator, test whether estimator construction itself is the dominant error source.

For the coalition game

`v(S) = y_factual - E[f(do(X_S ~ q))]`,

the Shapley marginal for candidate `i` after predecessor set `S` is

`m_i(S) = v(S∪{i}) - v(S)`.

A coupled Monte-Carlo estimate uses the same sampled intervention values for all members of `S` in both terms and changes only `i` in the expanded coalition. If `f` is structurally invariant to `i`, the paired marginal is exactly zero for every draw. This is stronger than merely having small estimator variance.

## Central hypotheses

### H1 — coupling defect
At matched structural-evaluation budget, a common-random-number chain estimator (`CRN_CHAIN_MC`) will have lower exact-teacher RMSE and lower false-credit mass than the legacy independent-resampling estimator (`LEGACY_INDEPENDENT_MC`) on the single-cause S01 family.

### H2 — structural-null property
Under a correct structural evaluator, any candidate absent from the structural outcome equation must receive zero paired marginal contribution under `CRN_CHAIN_MC` and `ANTITHETIC_CRN_MC` up to floating-point tolerance (`1e-12`) for every frozen seed, context and budget.

### H3 — antithetic variance reduction
At matched structural-evaluation budgets on a two-cause interaction family, `ANTITHETIC_CRN_MC` must reduce exact-teacher mean-squared error relative to `CRN_CHAIN_MC` on the aggregate primary endpoint. Failure does not invalidate CRN coupling; it invalidates the antithetic qualifier.

### H4 — variance-only authority is invalid
Estimator variance alone cannot certify causal authority. Under a deliberately misspecified structural evaluator, an estimator may have arbitrarily low/zero Monte-Carlo variance while converging to false causal credit. This is a mandatory counterexample, not an optional exploratory result.

### H5 — causal direction is context conditional
On a held-out sign-flip family, pooled global signed credit is not allowed to issue a single global causal direction when the exact/estimated sign differs by context. The admissible state is `CONTEXT_CONDITIONAL_ONLY` or abstention.

## Estimators

1. `EXACT_TEACHER` — exact coalition integration; evidence teacher only.
2. `LEGACY_INDEPENDENT_MC` — frozen historical approximation semantics for comparison.
3. `CRN_CHAIN_MC` — uniformly sampled permutations with nested coalitions evaluated using common random numbers; predecessor assignments are reused.
4. `ANTITHETIC_CRN_MC` — CRN chain plus paired complementary intervention assignments.
5. `DOUBLE_ANTITHETIC_CRN_MC` — exploratory: complementary assignments and reverse permutation pairing. It has no primary PASS authority.

No RPE-prioritized proposal is used in the primary estimator because RPE is not the target causal estimand. Any future non-uniform proposal must include a proven/verified importance correction.

## Environments

### E0 — SINGLE_CAUSE_CONFOUNDED
Candidates `A,B,C,D`. Only `A` enters the structural outcome. `C` is a noisy proxy for latent `U`; `B` is temporally correlated with `A`; `D` is random. Contexts reproduce strong confounding, weak confounding, and sign-inverted proxy structure.

### E1 — TWO_CAUSE_INTERACTION
`A` and `B` are structural causes; `C,D` are non-causes. Outcome includes a context-dependent `A×B` interaction. This prevents the antithetic estimator from winning merely because the game is additive.

### E2 — CONTEXT_SIGN_FLIP
Only `A` is a candidate cause, but its signed effect reverses with context. Absolute leverage remains non-zero. This family tests whether a global signed authority silently averages incompatible mechanisms.

### E3 — PRECISELY_WRONG_MODEL
Ground truth excludes `C`, while the evaluated counterfactual model includes a shared spurious `C` edge chosen to preserve good factual fit when `C≈A`. This tests the decomposition

`hat_phi_M - phi_true = (hat_phi_M - phi_M) + (phi_M - phi_true)`

where the first term is structural-model error and the second is estimator error.

## Frozen cohorts

- CALIBRATION/DEBUG: seeds `41000..41031` — implementation diagnostics only; no confirmatory metric may be tuned after primary execution.
- PRIMARY: seeds `42000..42127` — 128 seeds.
- INDEPENDENT_REPLICATION: seeds `52000..52127` — 128 seeds.
- 64 factual rows per context/seed for E0/E1/E2 unless the implementation records a lower fail-closed count before PRIMARY.

## Structural-evaluation budgets

Per factual row: `8, 16, 32, 64, 128, 256` maximum structural model evaluations.

Estimator-specific permutation/pair counts are derived mechanically from actual model evaluations per path. Actual evaluations, not requested budgets, are ledgered.

## Primary endpoints

For each estimator/environment/budget:

- exact-teacher vector RMSE;
- component bias;
- component sampling variance across repeated estimator replicates;
- false-credit mass on structurally null candidates;
- causal top-set recovery;
- signed-credit error;
- actual structural evaluations;
- wall-clock time.

For E2 additionally:

- context sign recovery;
- global sign stability;
- authority state.

For E3 additionally:

- estimator variance around the misspecified-model teacher;
- error of misspecified-model teacher relative to true teacher;
- false causal mass despite low estimator variance.

## Variance diagnostic — NOT an authority rule

The historical proposed variance ceiling is corrected to the actual S01 exact gap `Delta0 = 1.0`, not `0.5`.

Using `delta = Delta0/4 = 0.25`, `alpha_FWER = 1e-4`, four simultaneous components, and a Normal diagnostic only:

- `z = 4.214799669993038`
- `sigma_max = 0.0889722001901503`
- `variance_max = 0.00791605240667618`

This is retained only as a diagnostic screen. **It is prohibited as a causal-authority guarantee**, because structural model bias can be non-zero even when estimator variance is zero.

## Confirmatory predicates

`CSCA_03_COUPLED_ESTIMATOR_QUALIFIED` requires all:

1. E0: `CRN_CHAIN_MC` false-credit mass on `B,C,D` <= `1e-12` for every PRIMARY and REPLICATION seed×context×budget unit.
2. E0: `CRN_CHAIN_MC` exact-teacher aggregate RMSE is strictly lower than `LEGACY_INDEPENDENT_MC` at every budget in PRIMARY and REPLICATION.
3. E0: causal top-set recovery for CRN is `1.0` at every budget in PRIMARY and REPLICATION.
4. E1: CRN false-credit mass on null candidates `C,D` <= `1e-12` for every unit.
5. E1: `ANTITHETIC_CRN_MC` aggregate MSE <= `0.90 × CRN_CHAIN_MC` aggregate MSE at at least four of six matched budgets in PRIMARY and independently in REPLICATION.
6. E2: any context sign inversion forces `CONTEXT_CONDITIONAL_ONLY`; `GLOBAL_DIRECTION_ACCEPT` count must equal zero.
7. E3: experiment demonstrates that estimator variance can decrease without eliminating structural false credit; therefore `VARIANCE_ONLY_AUTHORITY` must be recorded as falsified/not-supported.
8. No threshold or budget is changed after PRIMARY results are observed.

If predicates 1–4 fail: `CSCA_03_COUPLED_ESTIMATOR_NOT_QUALIFIED`.

If 1–4 pass but predicate 5 fails: `CSCA_03_COUPLED_QUALIFIED_ANTITHETIC_NOT_QUALIFIED`.

If 1–6 pass and mandatory E3 counterexample is successfully demonstrated: `CSCA_03_COUPLED_ESTIMATOR_QUALIFIED`.

## Nulls / adversarial attacks

- N1 zero causal effect;
- N2 correlation only;
- N3 temporal distractor;
- N4 proxy stronger observationally than true cause;
- N5 context sign inversion;
- N6 two-cause interaction;
- N7 shared spurious model edge;
- N8 factual-fit-good / intervention-wrong model;
- N9 budget starvation;
- N10 seed replication.

## Kill conditions

- Any non-cause gets non-zero CRN paired marginal under a correct evaluator beyond `1e-12`.
- CRN is not better than legacy independent resampling on E0 at matched budgets.
- Context sign inversion produces global directional authority.
- Result artifacts cannot reproduce from frozen commit+seed+protocol.

## Scientific boundary

A PASS would qualify only an estimator construction under controlled SCMs. It would **not** establish counterfactual-model adequacy, real-LM benefit, biological equivalence, shadow-inference authority, replay utility, or physical compute benefit.
