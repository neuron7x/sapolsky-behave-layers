# Preregistration — Resolution-Aware Causal Debt V2

Frozen before the V2 debt rule is implemented or V2 results are observed.

## Parent result

`CAUSAL_DEBT_CONTROL_NOT_QUALIFIED` from V1 is binding and must remain unchanged.

## Frozen environments

`proxy` and `descendant`, each evaluated under `same`, `decorrelated`, `reversed`
contexts. The true outcome mechanism is always `C -> Y` with 10% outcome noise.
`S` never enters the outcome equation.

## Seeds

Same 20 seeds as V1.

## Budgets

`[4, 8, 16, 32]`.

## Policies

Primary: `causal_debt_v2_cf`.
Matched-CF controls: `uniform_cf`, `rpe_cf`.
Oracle reference: `oracle_invariant`.

All CF policies receive the identical structural intervention operator,
consolidation gate, candidate set and replay budget.

## Primary endpoint

Per seed, average OOS accuracy over both environment variants and all four budgets.
Two paired comparisons: V2 vs uniform-CF and V2 vs RPE-CF. Exact random-sign max-T
family-wise correction, alpha 0.05.

## Additional frozen gates

A CONTROL-ONLY qualification requires all:

1. positive aggregate OOS difference vs both matched-CF controls;
2. FWER p <= 0.05 for both primary comparisons;
3. benign `proxy` median OOS non-inferiority vs RPE-CF within 0.02;
4. superiority vs RPE-CF in the `descendant` environment in >= 3/4 budgets;
5. aggregate invariant-cause recall >= each matched-CF control;
6. false-credit rate <= each matched-CF control + 0.05;
7. no biological or VIA ascension authority.

Any failure -> `CAUSAL_DEBT_V2_CONTROL_NOT_QUALIFIED`.
