# Preregistration — Causal Debt Ledger V1

Frozen before implementation results are inspected.

## Environment

Binary structural environment with:

- invariant cause `C`;
- spurious correlate `S` whose observational association with `Y` is strong in the
  acquisition context but changes sign or vanishes under held-out regimes;
- nuisance feature `N`;
- binary outcome `Y` generated from `C` plus bounded noise.

Training/acquisition contexts induce `S <- C` with context-specific sign. The true
outcome mechanism never reads `S`.

## Candidate set

Exactly `cause:C`, `spurious:S`, `nuisance:N`. All policies receive the same candidates.

## Replay budgets

`[4, 8, 16, 32, 64]` interventions/updates per episode.

## Seeds

`[101, 211, 307, 401, 503, 601, 701, 809, 907, 1009, 1103, 1201, 1301, 1409, 1511, 1601, 1709, 1801, 1901, 2003]`.

## Policies

`fifo_obs`, `rpe_obs`, `uncertainty_obs`, `uniform_cf`, `rpe_cf`, `causal_debt_cf`,
plus `oracle_invariant` reference.

## Fairness contract

For a given seed and budget:

- same acquisition data;
- same candidate initialization;
- same replay budget;
- same structural counterfactual evaluator for all `*_cf` policies;
- same consolidation thresholds;
- same held-out evaluation set;
- only scheduling / credit-update policy may differ.

## Statistics

Per seed, compute paired differences in OOS accuracy and false-credit indicators.
Use an exact/random-sign paired permutation test across seeds. Correct the two primary
OOS comparisons with max-T family-wise correction. Report medians and per-budget
replication. No post-hoc seed removal.

## Non-authorization

Even a PASS is a synthetic control qualification only and may not authorize VIA-V2+
or a biological/mechanistic claim.
