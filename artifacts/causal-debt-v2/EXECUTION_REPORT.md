# Resolution-Aware Causal Debt V2 — Execution Report

Date: 2026-08-10
Verdict: `CAUSAL_DEBT_V2_CONTROL_QUALIFIED`
Scope: synthetic SCM control only

## Binding parent

V1 remains `CAUSAL_DEBT_CONTROL_NOT_QUALIFIED`. V2 does not overwrite or reinterpret
that negative result.

## Change under test

Only replay priority was conceptually corrected: observational eligibility decays
with accumulated intervention evidence, while measured causal leverage becomes the
priority term. Consolidation remains fail-closed and requires cross-context evidence.

The original V1 `debt()` function remains in code for reproducibility. V2 uses the
new `resolution_aware_debt()` path.

## Confirmatory design

20 frozen seeds × 4 budgets × 2 frozen SCM variants × 4 policies = 640 cells.

Matched counterfactual controls receive the same candidate set, replay budget,
structural intervention operator and consolidation gate.

## Primary result

Mean paired OOS advantage, averaged within seed over both variants and all budgets:

- versus `uniform_cf`: +0.16650390625;
- versus `rpe_cf`: +0.193157958984375.

Exact paired random-sign max-T FWER p-values:

- versus `uniform_cf`: 1.9073486328125e-06;
- versus `rpe_cf`: 9.5367431640625e-07.

All preregistered V2 gates passed.

Aggregate performance:

- `causal_debt_v2_cf`: mean OOS 0.8439, invariant recall 0.85625;
- `uniform_cf`: mean OOS 0.6774, invariant recall 0.4375;
- `rpe_cf`: mean OOS 0.6508, invariant recall 0.36875;
- invariant oracle: mean OOS 0.9016.

False-credit rate was 0 for all matched-CF methods, so the result is correctly
interpreted as improved *replay allocation / invariant-cause recovery*, not superior
false-positive control.

## Benign/adversarial decomposition

`proxy` (benign): V2 median OOS 0.8965; RPE-CF median OOS 0.8965. The preregistered
non-inferiority condition passed.

`descendant` (adversarial observational salience): V2 median OOS 0.8994; RPE-CF
median OOS 0.5093. V2 exceeded RPE-CF at all 4/4 frozen budgets.

## What this supports

Only a control-level computational statement: in this frozen synthetic benchmark,
a replay scheduler that allows negative intervention evidence to discharge
observational debt can recover an invariant cause more efficiently than matched
counterfactual replay controls.

## What this does not support

- no claim that biological replay performs this algorithm;
- no claim that language-model memory benefits;
- no real-workload claim;
- no GPU/inference efficiency claim;
- no VIA scientific ascension.

## Remaining attribution risk

V2 uses both resolution-aware candidate scheduling and deterministic least-covered
context selection. The confirmatory result establishes the *combined policy*, not
the independent causal contribution of those two submechanisms. A separate
non-confirmatory ablation is required before attributing the gain specifically to
debt discharge.
