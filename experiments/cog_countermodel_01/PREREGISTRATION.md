# COG-COUNTERMODEL-01 — Autonomous Observational Countermodel Search

**STATUS:** FROZEN BEFORE CONFIRMATORY EXECUTION  
**MODE:** PASSIVE FACTUAL DATA · NO NEW `do_env` · ADVERSARIAL MODEL SEARCH · FAIL-CLOSED

## Kill question

Given a surviving assumption-conditional causal candidate, can CWC autonomously construct causally different structural models that preserve the same factual law, and refuse causal consolidation while any such countermodel survives?

## Theorem under test

For the fitted reduced form

`X = a_x + lambda'R + eps_x`

`Y = a_y + delta'R + eps_y`,

for any proposed structural coefficient `b`, define

`eta_b = delta - b lambda`, `U_x=eps_x`, `U_y=eps_y-b eps_x`.

Then

`Y = b X + (a_y-b a_x) + eta_b'R + U_y`

reconstructs the same factual path exactly. In the linear-Gaussian interpretation the induced reduced-form distribution is identical. Therefore factual data alone do not identify `b` when direct regime effects and latent X-Y dependence are unrestricted.

## Search contract

- Input state must be exactly `CAUSAL_CANDIDATE_UNDER_ASSUMPTIONS`; any weaker upstream state is ineligible.
- Frozen beta grid: `[-0.5, 2.0]` in steps of `0.025` (101 points).
- A countermodel must differ from the candidate by at least `0.49` in beta.
- Exact-equivalence tolerance: path reconstruction error `<=1e-10`; analytic observational KL is zero by reparameterization.
- No universal scalar "countermodel cost" is invented. Countermodels are compared on a Pareto vector: direct-effect L2 debt, absolute latent residual correlation, causal displacement.
- An explicit exclusion-style structural bound may restrict `||eta||_2 <= 0.08`; uniqueness under this bound is assumption-conditional only and never grants causal authority.

## Frozen synthetic families

All use the CSCA-08 structural family with true environment coefficient `beta=0.8`, regime loadings `(0.9,0.5)`, latent X-Y confounding, 4096 rows/seed.

- `C0_VALID`: exclusion holds (`k=0`), normal aleatoric noise.
- `C1_COORDINATED_EXCLUSION`: direct effect `k*lambda`, `k=0.5`; IV-style observable candidate is near `1.3` although environment beta remains `0.8`.
- `C2_ALEATORIC_HIGH`: exclusion holds, outcome noise sd `3.0`.
- `C3_UPSTREAM_INVALID`: regime assignment is confounded with latent U; countermodel search must refuse upstream promotion rather than manufacture a stronger state.

PRIMARY seeds: `71000..71063`.  
Independent REPLICATION seeds: `81000..81063`.  
Development/unit-test seeds are disjoint and forbidden from confirmatory scoring.

## Primary metrics and pass predicates — BOTH cohorts independently

1. `C0_VALID`: unrestricted exact-countermodel survival rate `>=0.99`; zero unconditional causal authority.
2. `C0_VALID`: under declared exclusion bound, at least `0.95` of seeds have no causally shifted countermodel within bounds, but the state must be `ASSUMPTION_CONDITIONAL_IDENTIFICATION_COUNTERMODELS_OUTSIDE_BOUNDS`, never causal truth.
3. `C1_COORDINATED_EXCLUSION`: unrestricted exact-countermodel survival rate `>=0.99`; at least `0.95` of seeds contain a Pareto countermodel within `|beta-0.8|<=0.03`.
4. `C1_COORDINATED_EXCLUSION`: maximum path reconstruction error of the recovered near-0.8 alternative `<=1e-10`.
5. `C2_ALEATORIC_HIGH`: unrestricted exact-countermodel survival rate `>=0.99`; noise alone must not erase the equivalence class.
6. `C3_UPSTREAM_INVALID`: `>=0.95` return `UPSTREAM_CANDIDATE_NOT_ELIGIBLE`; zero authority.
7. Across every family/seed, `causal_authority_granted` must be false.
8. At least one non-empty Pareto frontier must be produced in every eligible seed.

## Failure interpretation

- Failure to find C0/C1/C2 countermodels means the generator is too weak and cannot protect consolidation.
- Treating the exclusion-constrained result as factual proof fails the experiment even if all numerical metrics pass.
- Running the generator as an authority-upgrading step after an invalid upstream candidate fails closed.

## Non-promotion boundary

A PASS licenses only `AUTONOMOUS_COUNTERMODEL_GENERATOR_QUALIFIED_SYNTHETIC_NARROWED`. It does not establish semantic causality, real-trace identification, replay control, active control, or architecture promotion. Its purpose is adversarial: preserve causal ambiguity when a factual-law-preserving alternative exists.
