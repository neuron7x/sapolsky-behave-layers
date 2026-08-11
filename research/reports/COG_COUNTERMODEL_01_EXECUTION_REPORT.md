# COG-COUNTERMODEL-01 — Execution Report

**Verdict:** `AUTONOMOUS_COUNTERMODEL_GENERATOR_NOT_QUALIFIED`  
**Authority:** `NO_PROMOTION`

## What passed

The algebraic generator itself behaved as intended on every eligible confirmatory seed:

- unrestricted exact factual-law countermodels survived in `64/64` C0, C1 and C2 seeds in both PRIMARY and REPLICATION;
- strict exclusion bounds produced assumption-conditional uniqueness in `64/64` C0 seeds in both cohorts;
- high aleatoric noise did not erase the exact equivalence class (`64/64` in both cohorts);
- invalid upstream causal candidates were refused `64/64` in both cohorts;
- unconditional causal authority count was exactly zero;
- factual path reconstruction error on Pareto survivors remained at floating-point scale (worst approximately `3.55e-15`).

## Frozen predicate that failed

The preregistration required the **Pareto frontier** for C1 coordinated exclusion to contain a countermodel near the environment's hidden `beta=0.8` in at least 95% of seeds.

Observed:

- PRIMARY: `32/64 = 0.50`;
- REPLICATION: `41/64 = 0.640625`.

The threshold is not weakened and the experiment remains failed.

## Why the failure is scientifically useful

The failed predicate accidentally asked a passive ambiguity-preserving mechanism to select the privileged ground-truth member of an observational equivalence class. That is incompatible with the CSCA-07 boundary: factual equivalence contains no information that marks `beta=0.8` as semantically true.

Two additional design effects sharpen the problem:

1. Pareto pruning minimizes assumption-debt axes, not truth error, so the true generator need not lie on the Pareto frontier.
2. The frozen `min_causal_shift=0.49` is nearly equal to the planted `0.5` coefficient gap; sampling variation in the upstream candidate can make the exact 0.8 grid point ineligible even though it remains algebraically observationally equivalent.

Therefore COG-COUNTERMODEL-01 is retained as a **design-negative**. The generator must represent the surviving causal equivalence **set**, not be graded by hidden-truth recovery.

## Required repair

A new experiment ID must be preregistered with fresh seeds. It must:

- preserve the full exact-equivalence set separately from any Pareto decision frontier;
- derive assumption-conditional beta intervals analytically where possible;
- use causal-set diameter / existence of materially distinct exact alternatives as the primary ambiguity metric;
- explicitly forbid truth-selection metrics inside an observational equivalence class;
- keep the original negative artifacts immutable.
