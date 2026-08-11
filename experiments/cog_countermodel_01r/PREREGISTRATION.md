# COG-COUNTERMODEL-01R — Set-Valued Countermodel Qualification

**STATUS:** FROZEN BEFORE CONFIRMATORY EXECUTION  
**PARENT:** `COG-COUNTERMODEL-01` = `AUTONOMOUS_COUNTERMODEL_GENERATOR_NOT_QUALIFIED`  
**MODE:** PASSIVE FACTUAL DATA · NO NEW `do_env` · SET-VALUED IDENTIFICATION · FAIL-CLOSED

## Repair rationale

The parent experiment failed because it required the Pareto frontier to recover the hidden generator coefficient `beta=0.8`. That is not a valid passive-identification objective: Pareto pruning ranks assumption-debt axes, not semantic truth, and observational equivalence provides no information selecting the privileged member. The parent threshold remains failed and immutable.

R1 tests the proper cognitive function: **represent and preserve the surviving causal equivalence set**, and narrow it only under explicitly declared structural bounds.

## Frozen mathematical object

For reduced form

`X = a_x + lambda'R + eps_x`,

`Y = a_y + delta'R + eps_y`,

all real `b` admit the exact reparameterization

`eta_b = delta - b lambda`, `U_y = eps_y - b eps_x`.

Therefore the unrestricted structural beta set is `R` (all real beta) within this model class.

For a declared direct-effect bound `||eta_b||_2 <= epsilon`, R1 solves the quadratic inequality analytically and returns an assumption-conditional beta interval. This interval is not evidence that the bound is true.

## Frozen search / materiality constants

- finite diagnostic beta grid: `[-0.5, 2.0]`, 101 points, step `0.025`;
- material causal displacement: `Delta_beta = 0.40`;
- declared direct-effect bound for the constrained diagnostic: `epsilon_eta = 0.15`;
- exact path tolerance: `1e-10`.

`Delta_beta=0.40` is a substantive effect-disagreement threshold, not a truth-recovery tolerance. It is separated from the planted coordinated-exclusion gap `0.5` and is frozen before R1 results.

## Frozen synthetic families

Same structural generator family as the parent, 4096 factual rows/seed:

- `R0_VALID`: exclusion holds, normal outcome noise;
- `R1_COORDINATED_EXCLUSION`: environment beta `0.8`, direct effect `0.5*lambda`; observable IV-style candidate near `1.3`;
- `R2_ALEATORIC_HIGH`: exclusion holds, outcome noise sd `3.0`;
- `R3_UPSTREAM_INVALID`: regime assignment confounded with latent U.

Fresh PRIMARY seeds: `91000..91063`.  
Fresh independent REPLICATION seeds: `101000..101063`.  
No parent/development seed may enter R1 scoring.

## Primary pass predicates — BOTH cohorts independently

For every eligible family `R0/R1/R2`:

1. unrestricted set kind is `ALL_REAL_BETA_UNDER_UNRESTRICTED_REPARAMETERIZATION` in `64/64` seeds;
2. a materially shifted exact finite-grid countermodel survives in `>=0.99` of seeds;
3. finite-grid exact-countermodel diameter is `>=1.0` in `>=0.99` of seeds;
4. non-empty Pareto frontier rate is `1.0`;
5. maximum factual path reconstruction error on the frontier is `<=1e-10`;
6. unconditional causal authority count is exactly zero.

For `R0_VALID` and `R1_COORDINATED_EXCLUSION` under the declared `epsilon_eta=0.15` direct-effect bound:

7. analytic beta interval exists in `>=0.95` of seeds;
8. interval width is `<0.40` in `>=0.95` of seeds;
9. no beta inside that interval differs from the upstream candidate by `>=0.40` in `>=0.95` of seeds;
10. runtime state is `ASSUMPTION_CONDITIONAL_IDENTIFICATION_COUNTERMODELS_OUTSIDE_BOUNDS` in `>=0.95` of seeds.

For `R2_ALEATORIC_HIGH` the unrestricted equivalence-set predicates must still pass; no requirement is placed on the narrow direct-effect interval because finite-sample reduced-form noise can make the declared bound empirically empty.

For `R3_UPSTREAM_INVALID`:

11. `UPSTREAM_CANDIDATE_NOT_ELIGIBLE` rate `>=0.95`;
12. authority count zero.

## Forbidden success criteria

- Hidden true-beta recovery is not a qualification metric.
- Pareto membership of the generating model is not a qualification metric.
- Empty constrained interval does not falsify the environment; it falsifies compatibility with the declared bound at the fitted reduced form.
- No result may call the assumption-conditional interval causal truth.

## Terminal states

PASS: `SET_VALUED_COUNTERMODEL_GUARD_QUALIFIED_SYNTHETIC_NARROWED`  
FAIL: `SET_VALUED_COUNTERMODEL_GUARD_NOT_QUALIFIED`

Even PASS authorizes only a countermodel/consolidation guard. Semantic causality, real-trace identification, replay control, active control and architecture promotion remain blocked.
