# CWC-CDL-01 — Deferred Causal Credit Ledger

Status: EXPERIMENTAL / NON-ASCENSION / FALSIFICATION-FIRST
Date: 2026-08-10

## Intent

Test a narrow computational hypothesis: a memory system can defer causal credit,
prioritize unresolved candidates for replay, attack them with matched
counterfactual perturbations, and consolidate only cross-context invariant causes.

This act does **not** claim that the brain implements this algorithm, that replay is
counterfactual causal inference, or that CWC scientific ascension is authorized.
The neuroscience analogy is motivation only; the executable claim is computational.

## Core hypothesis

Under a regime-shift environment containing one invariant cause and one initially
predictive but non-causal correlate, a causal-debt replay policy should reduce
false consolidation and improve held-out prediction relative to replay policies
that receive the same candidate set, replay budget, and counterfactual operator but
lack debt/invariance prioritization.

## First-principles decomposition

A candidate dependency is not immediately converted into policy credit.

1. **Eligibility** preserves a weak candidate relation.
2. **Debt** increases when the candidate is consequential but unresolved.
3. **Replay** spends a bounded offline budget on unresolved debt.
4. **Counterfactual attack** suppresses the candidate while holding the structural
   context fixed and measures outcome leverage.
5. **Cross-context invariance** asks whether leverage survives regime changes.
6. **Precision** rises only with repeated, directionally coherent intervention evidence.
7. **Consolidation** is fail-closed: unresolved or context-fragile candidates remain
   non-authoritative.

## Mandatory controls

The confirmatory experiment must include:

- FIFO observational replay;
- RPE-priority observational replay;
- uncertainty-priority observational replay;
- uniform counterfactual replay (same intervention oracle as CDL);
- RPE-priority counterfactual replay (same intervention oracle as CDL);
- causal-debt counterfactual replay;
- an oracle-invariant upper reference, excluded from statistical comparisons.

The two counterfactual controls prevent a capability-confound: CDL may not claim a
scheduler advantage merely because only CDL was allowed to intervene.

## Frozen primary endpoints

1. held-out regime-shift prediction accuracy;
2. false-credit rate: spurious candidate consolidated with authoritative precision;
3. invariant-cause recall;
4. causal-vs-spurious credit margin.

Primary comparison: `causal_debt_cf` versus `uniform_cf` and `rpe_cf` under exactly
matched replay budgets.

## Confirmatory acceptance rule

A CONTROL-ONLY qualification requires all of:

- median OOS accuracy of `causal_debt_cf` strictly exceeds both matched-CF controls;
- family-wise permutation p <= 0.05 for the two OOS comparisons;
- false-credit rate is lower than both matched-CF controls;
- invariant-cause recall is not lower than either matched-CF control;
- the result holds in at least 4/5 preregistered replay budgets;
- no descendant VIA level is authorized.

Failure of any condition yields `CAUSAL_DEBT_CONTROL_NOT_QUALIFIED`.

## Scope limit

Synthetic SCM only. No claim about biological replay, general intelligence,
real-language-model workloads, GPU efficiency, or production memory systems.
