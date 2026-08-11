# CSCA-08A/B — Observational Identifying-Contract Theory

## 1. Why this gate exists

CSCA-07 proved the no-assumption boundary: if two latent causal models induce the same factual trace law, passive compute cannot choose between them. CSCA-08 therefore does not ask passive replay to create missing causal information. It adds one explicit auxiliary structure and tracks exactly what that structure licenses.

## 2. Frozen model class

Let `R=(R1,R2)` be observed heterogeneous regime coordinates, `U` an unobserved common cause, `X` a candidate cause/treatment, `Y` the target outcome and `W` a negative-control outcome.

`X = lambda'R + gamma U + eps_x`

`Y = beta X + delta U + eta'R + eps_y`

`W = kappa U + eps_w`

The narrow identifying contract sets `eta=0`, requires regime relevance, and assumes regime exogeneity. Under zero-mean independent R and exogenous noises,

`Cov(R_j,Y) = beta Cov(R_j,X)`

for every relevant coordinate j, hence

`beta = Cov(R_j,Y) / Cov(R_j,X)`.

This identifies a homogeneous linear causal-effect candidate inside the declared model class despite latent X-Y confounding.

## 3. Assumption type system

The implementation refuses to treat assumptions as one undifferentiated confidence scalar.

- A1 relevance: empirically falsifiable from `R-X` association.
- A2 exogeneity: only partially falsifiable; association with negative-control `W` can reject some violations, never prove all of them absent.
- A3 exclusion: not generally testable from this factual channel.
- A4 effect invariance: partially falsifiable by disagreement among independent regime-specific Wald estimands.
- A5 regime-label reliability: requires provenance; symmetric label corruption can preserve moment ratios.

Therefore the strongest machine state is `CAUSAL_CANDIDATE_UNDER_ASSUMPTIONS`. `TRUE_CAUSAL_EFFECT` is intentionally not in the state space.

## 4. Exact coordinated-exclusion impossibility construction

Take a noiseless treatment equation for clarity:

`X = lambda'R + gamma U`.

An exclusion-violating model is

`Y = beta X + delta U + k lambda'R + eps_y`.

Since `lambda'R = X-gamma U`, the identical factual path can be rewritten as

`Y = (beta+k)X + (delta-k gamma)U + eps_y`.

Thus an invalid model with direct `R->Y` effect and coefficient `beta` is pathwise observationally identical to a no-direct-effect model with coefficient `beta+k`. The confirmatory implementation instantiates `beta=.8`, `k=.5`, yielding alternative coefficient `1.3` with maximum Y-path discrepancy `1.78e-15`.

Consequences:

1. instrument agreement is a falsifier of heterogeneous exclusion violations, not proof of exclusion;
2. a negative control is a falsifier of some exogeneity violations, not proof of exogeneity;
3. more passive compute cannot resolve this exact equivalence;
4. any later real-trace promotion must bind external assignment/provenance evidence to the assumption contract.

## 5. Cognitive-runtime consequence

The architectural primitive is not an IV estimator. It is an **assumption-typed causal candidate**: every causal estimate carries its unresolved identifying debt. Downstream memory, replay and planning modules must be able to inspect that debt and abstain from treating the candidate as environment-causal truth.
