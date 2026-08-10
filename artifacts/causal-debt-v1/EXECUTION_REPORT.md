# Causal Debt Ledger V1 — Execution Report

Date: 2026-08-10
Verdict: `CAUSAL_DEBT_CONTROL_NOT_QUALIFIED`
Scope: synthetic SCM control only

## What was tested

The preregistered `causal_debt_cf` scheduler was compared against FIFO/RPE/
uncertainty observational replay and, critically, two matched counterfactual
controls (`uniform_cf`, `rpe_cf`) that received the same structural intervention
operator and replay budgets.

20 frozen seeds × 5 replay budgets × 7 policies = 700 cells.

## Primary result

The causal-debt scheduler failed the preregistered qualification criteria.
Aggregated over frozen budgets/seeds:

- `causal_debt_cf`: median OOS accuracy 0.5049; invariant recall 0.18;
- `uniform_cf`: median OOS accuracy 0.5361; invariant recall 0.48;
- `rpe_cf`: median OOS accuracy 0.8984; invariant recall 0.84.

Max-T paired family-wise p-values for the two primary OOS comparisons were both
1.0 in the positive direction. There is no positive scheduler claim.

## Mechanistic diagnosis (post-hoc; non-confirmatory)

The failure exposed a defect in the debt definition. `debt()` contained an
`eligibility - lower_confidence` term. A candidate with strong observational
association but repeated *zero* counterfactual effect therefore retained large
unresolved debt indefinitely. The scheduler repeatedly replayed the already
causally unsupported spurious candidate and starved the invariant cause.

Example frozen traces show the pattern directly: some seeds spent 30/32 replay
steps on `S` while `C` remained at two probes and could not pass the minimum replay
gate.

This is a substantive algorithmic failure, not a statistical accident.

## Protocol defect discovered

The V1 acceptance rule also required `causal_debt_cf` to have a *strictly lower*
false-credit rate than both matched-CF controls. In the frozen SCM, interventions
on non-causes are deterministic zero-effect probes, and both matched-CF controls
already achieved false-credit rate 0.0. Strict improvement below zero is
mathematically impossible.

Therefore V1 was capable of rejecting the method but its full positive acceptance
conjunction was not attainable in this benchmark. This does not alter the negative
verdict; it blocks any attempt to reinterpret V1 as a fair positive qualification.

## First-principles correction implied by the failure

Causal debt must be *dischargeable by negative causal evidence*. Observational
eligibility may create a candidate, but it cannot keep an interventionally dead
candidate permanently high-priority. A second experiment must distinguish:

- unresolved debt;
- positive causal credit;
- resolved-null debt.

The next protocol must use false-credit as a non-inferiority/safety constraint,
not an impossible strict-improvement criterion when matched controls are already
at the floor.

## Authorization

No biological claim. No real-workload claim. No VIA ascension. V1 remains sealed
as a negative result and must not be overwritten by V2.
