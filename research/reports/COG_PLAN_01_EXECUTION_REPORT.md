# COG-PLAN-01 — Execution Report

**Date:** 2026-08-11  
**Preregistration commit:** `4c1489a1a7102827a7f3de701af04aaee08de396`  
**Verdict:** `PROOF_CARRYING_COUNTERFACTUAL_PLANNER_QUALIFIED_SYNTHETIC_NARROWED`  
**Authority:** `PLANNING_SAFETY_PRIMITIVE_ONLY`

## Objective

Vertically integrate typed epistemic state, assumption-aware memory, surviving
countermodels and the certified information-acquisition governor into one action
selection boundary without allowing hidden world averaging or stale evidence.

## Confirmatory design

PRIMARY `seed_base=83001`, REPLICATION `seed_base=93001`, 128 cases/family/cohort,
12 frozen families (`P0..P11`), robust margin `0.05`.

The families test robust dominance, world reversal, a hidden averaging trap,
decision-invariant surviving countermodels, assumption-conditional plans, information
acquisition, insufficient budget, zero-information channels, margin ties, stale memory,
dropped countermodels and legacy/retracted memory.

## Result

Every `P0..P11` family passed `128/128` in PRIMARY and `128/128` in REPLICATION.

Across both cohorts:

- false `ROBUST_ACTION` count in unsafe families: `0`;
- certificate-binding failures before intended invalidation: `0`;
- certificate digest nondeterminism: `0`;
- mutated-world certificate acceptance: `0`;
- stale-memory certificate acceptance (`P9`): `0.0`;
- dropped-world certificate acceptance (`P10`): `0.0`;
- causal-truth fields in certificates: `0`;
- `P5` requested information in every case when the certified converse budget was
  feasible;
- `P6/P7` abstained in every case under insufficient budget / zero identifying rate;
- `P4` emitted assumption-conditional plans, never unconditional action authority;
- `P3` allowed a robust decision despite unresolved causal worlds only because the
  same action dominated in every explicitly represented world.

Gate self-test killed `7/7` frozen authority mutations.

## Interpretation

The important result is not that CWC found a true causal model. It did not. The result
is that unresolved causal-model ambiguity can remain explicit while a decision is
made only when the action itself is invariant across that ambiguity. When the action
is not identified, the system either asks for certified information or abstains.

## Non-promotion boundary

No semantic causal truth, real-world planning utility, replay value, active control,
autonomous self-modification, large-model transfer, architecture Pareto advantage or
external third-party replication is authorized.
