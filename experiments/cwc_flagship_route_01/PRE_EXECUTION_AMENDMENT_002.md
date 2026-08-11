# CWC-FLAGSHIP-ROUTE-01 — Pre-Execution Amendment 002

Date frozen: 2026-08-11
Status: PRE-EXECUTION / NO MODEL OUTPUTS OBSERVED
Parent preregistration commit: `cc1609ad6b944c613737c8103fc3d695ec9b31c9`
Amendment 001 commit: `bbf2ef90eafefd19b7f60e185d82b26c95f795dc`

## Pareto-frontier ambiguity found before implementation

The parent text said `FIXED_FRONTIER` is the convex depth1/depth2 mixture at the candidate's exact
FLOP spend. That can be anti-conservative: if depth2 is worse than depth1, an exact-spend rule forces
the baseline to waste compute and degrade quality. A compute budget is a maximum resource allowance,
not an obligation to consume every FLOP.

## Frozen repair

For budget `B`, `FIXED_FRONTIER(B)` is the minimum achievable mean CE among depth1/depth2 convex
mixtures whose expected logical FLOPs are **<= B**. Therefore a dominated deeper operating point can
never make the baseline worse merely because more budget is available.

With two fixed depths this is the monotone lower envelope of:

- depth1 point `(C1, L1)`;
- every convex mixture between `(C1, L1)` and `(C2, L2)`;
- depth2 point `(C2, L2)`.

Candidate superiority remains strict: `candidate_loss < FIXED_FRONTIER(candidate_compute)`.

## Frozen calibration slope

The family-specific opportunity-cost slope is:

`frontier_gain_per_flop = max(0, (L1 - L2) / (C2 - C1))`.

`DECISION_RELEVANT` continues iff:

`predicted_gain > frontier_gain_per_flop * B2`,

where `B2` is the incremental logical FLOP cost of the second Transformer block. The route cost `R`
is a constant tax charged by the final evaluator to every dynamic case; it is not hidden inside the
per-window threshold.

## Deterministic window collision rule

The parent SHA-derived offset is used first. If two requested windows map to the same start offset
within one file, increment modulo the valid offset count until the first unused offset is found.
This depends only on frozen source bytes and window index, never on model outputs.

All other parent/amendment-001 rules remain unchanged.
