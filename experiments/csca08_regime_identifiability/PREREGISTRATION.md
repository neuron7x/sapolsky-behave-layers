# CSCA-08A/B — Assumption-Typed Observational Regime Identification

**STATUS:** FROZEN BEFORE CONFIRMATORY EXECUTION  
**MODE:** PASSIVE FACTUAL DATA · NO NEW `do_env` · FAIL-CLOSED · ASSUMPTION-TYPED AUTHORITY

## Kill question
Can an observed heterogeneous regime channel add enough information to identify a causal-effect candidate under an explicit contract, while refusing to convert the surviving observable implications into unconditional causal truth?

## Identifying model class
Observed regime vector `R=(R1,R2)`; latent confounder `U`; treatment `X`; outcome `Y`; negative-control outcome `W`.

Valid synthetic family:

`R1,R2 independent Rademacher; U,eps independent Gaussian`

`X = lambda1 R1 + lambda2 R2 + gamma U + eps_x`

`Y = beta X + delta U + eps_y`

`W = U + eps_w`

Frozen true `beta=0.8`, `lambda=(0.9,0.5)`, `gamma=0.8`, `delta=1.0`, `sd_x=0.6`, `sd_y=0.8`, `sd_w=0.5`.

The causal candidate is the homogeneous linear coefficient `beta`, identifiable only under the declared IV-style assumption set.

## Assumptions and epistemic types
- A1 relevance: empirically falsifiable; at least two regime coordinates must shift `X`.
- A2 regime exogeneity: only partially falsifiable from factual data; `W` is a negative-control witness, not a proof.
- A3 exclusion `R -> Y` only via `X`: not testable in general from this factual channel.
- A4 common causal coefficient across regime coordinates: partially falsifiable via over-identification.
- A5 regime-label measurement reliability: provenance required; symmetric corruption can preserve Wald ratios.

No confirmatory outcome may grant unconditional causal authority.

## Estimator / observable attacks
For instrument j:

`beta_hat_j = Cov(R_j,Y) / Cov(R_j,X)`.

Influence-function standard errors are used for the Wald estimands. Relevance, negative-control association and pairwise instrument disagreement are tested with one Bonferroni family across the within-trace tests at `alpha=0.01`.

Possible runtime states:
- `IDENTIFYING_ASSUMPTION_VIOLATED`
- `INSUFFICIENT_INFORMATION_BUDGET`
- `CAUSAL_CANDIDATE_UNDER_ASSUMPTIONS`

There is deliberately no `TRUE_CAUSAL_EFFECT` or `CAUSAL_AUTHORITY_GRANTED` state.

## Frozen families
Each cohort has 128 fresh seeds/family, 4096 generated rows before any selection step.

- V0_VALID: contract holds.
- V1_DIRECT_NONPROPORTIONAL: direct `R1 -> Y` coefficient 0.5, `R2 -> Y` 0.
- V2_R_U_CONFOUNDING: both regime assignments depend on latent U.
- V3_ALEATORIC_HIGH: contract holds; `sd_y=3.0`.
- V4_SELECTION_BIAS: selection depends on `R1*U`.
- V5_WEAK_RELEVANCE: `lambda=(0.015,0.01)`.
- V6_COORDINATED_EXCLUSION: direct effects `(0.45,0.25)=0.5*lambda`; observable over-identification can survive despite true beta remaining 0.8.
- V7_LABEL_CORRUPTION: independent symmetric 25% flips applied to both observed regime labels after generation.

PRIMARY seeds: `50000..50127`.  
REPLICATION seeds: `60000..60127`.  
Pilot seeds `1000..1063` are forbidden from confirmatory reuse.

## Exact impossibility control
The pathwise coordinated-exclusion construction must produce two models with different causal coefficients `0.8` and `1.3` but identical factual `(R,X,Y,W)` arrays to numerical precision `<1e-12`. This is the proof that A3 cannot be promoted from surviving data-only checks.

## Primary pass predicates — BOTH cohorts independently
1. V0 candidate rate >= 0.95; assumption-violation rate <= 0.04; median `|beta_hat-0.8| <= 0.05`.
2. V1 assumption-violation rate >= 0.95.
3. V2 assumption-violation rate >= 0.95.
4. V3 candidate rate >= 0.90 and median `|beta_hat-0.8| <= 0.10`; high aleatoric noise must not be relabeled structural failure.
5. V4 assumption-violation rate >= 0.95.
6. V5 insufficient-information rate >= 0.95.
7. V6 candidate-under-assumptions rate >= 0.90, median `|beta_hat-0.8| >= 0.30`, causal authority exactly zero, and every candidate carries unresolved A3 exclusion debt.
8. V7 candidate-under-assumptions rate >= 0.90, causal authority exactly zero, and every candidate carries unresolved A5 measurement debt.
9. exact coordinated-exclusion path errors < 1e-12 and coefficient gap >= 0.49.
10. no family/seed may emit unconditional causal authority.

## Failure meaning
- If V0 fails: identifying instrument not qualified.
- If V1/V2/V4 fail: available falsification surface is too weak even for its declared scope.
- If V3 is systematically rejected: aleatoric uncertainty is being confused with structural violation.
- If V5 is accepted: compute/information abstention is fail-open.
- If V6 is promoted to unconditional truth: the experiment fails regardless of all accuracy metrics.

## Non-promotion boundary
A PASS can establish only `OBSERVATIONAL_IDENTIFYING_CONTRACT_QUALIFIED_SYNTHETIC_NARROWED`. It does not establish real-trace exogeneity/exclusion, semantic causality, replay control, active control, or architecture promotion.
