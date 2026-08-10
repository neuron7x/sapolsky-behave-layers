# CSCA-06A-IF — Interventional Falsifiability Under Latent Confounding and Aleatoric Noise

**Frozen before confirmatory execution:** 2026-08-10  
**Authority before run:** `SHADOW_RUNTIME_PATH_QUALIFIED_NARROWED`  
**Target:** qualify a *research-only falsification instrument*, not a graph-discovery oracle.

## Kill question

When factual fit and credit-estimator variance are both excellent, can the system distinguish a falsified causal **model class** from (i) admissible latent confounding, (ii) admissible aleatoric noise, and (iii) an interventionally indistinguishable alternative, while controlling false rejection under a finite intervention-cost budget?

## Non-negotiable identifiability boundary

No finite test can uniquely attribute a discrepancy to topology if arbitrary hidden confounding is permitted. The null therefore is the declared composite class

`P_M = { P(Y | do(X=a); M, eta) : eta in nuisance envelope }`.

The graph component is only conditionally falsified if the observed intervention law is separated from **every** member of this nuisance-closed class. Rejection of `P_M` is not proof that topology alone is wrong; an omitted nuisance mechanism outside the envelope remains an alternative explanation.

For the linear-Gaussian control family:

`Y = beta * do(X=a) + h + gamma U + epsilon`, with `U~N(0,1)`, `epsilon~N(0,sigma^2)`.

The scalar intervention law depends on `tau^2 = gamma^2 + sigma^2`. Therefore gamma and sigma are not separately identifiable from Y alone. This non-identifiability must be reproduced explicitly.

## Information-theoretic object

Do **not** use `I(M; do(X))` as a falsification threshold. The intervention is an action; evidence arrives in its outcome. Define, for intervention design d,

`D_M(d) = inf_{Q in P_M} KL(P_*^d || Q^d)`.

The cost-normalized falsifiability rate is

`R_M(d) = D_M(d) / Cost(d)`.

A model class is asymptotically unfalsifiable under the available interventions if the supremum attainable rate is zero. Positive rate is necessary for evidence to accumulate; finite-budget rejection still requires an error-controlled sequential test.

## Anytime-valid finite-budget test

For each frozen intervention block y under design d use

`e_block = q(y|d) / sup_{theta in P_M} p_theta(y|d)`

with a preregistered normalized mixture density q. For every theta in the composite null, pointwise `sup p >= p_theta`, hence `E_theta[e_block | past] <= 1`. The cumulative product is a test supermartingale. Reject at `E >= 1/alpha`, alpha=0.01. Optional stopping and early rejection are allowed; post-hoc alpha changes are forbidden.

This is deliberately conservative: nuisance parameters are profiled independently per block. Power is secondary to validity.

## Design

Actions: `do(X=-1)` and `do(X=+1)`, each unit cost. A pre-preregistration **design pilot** (separate seeds, non-authoritative) is permitted solely to choose block granularity for the conservative e-process; its data may never appear in PRIMARY/REPLICATION metrics. Analytic minimax KL/cost design selection is also recorded.

Frozen confirmatory block: 8 samples at each extreme intervention (16 samples, cost 16). Maximum 16 blocks (cost 256).

Alternative test density q is an equal mixture over slopes `{-0.8,-0.4,+0.4,+0.8}`, intercepts `{-0.5,0,+0.5}`, and SDs `{0.8,1.2,1.8}`. This mixture is fixed before confirmatory execution and carries no causal authority.

Composite nuisance envelope: shared intercept `h in [-0.75,0.75]`, interventional SD `tau in [0.5,2.5]`.

## Frozen families

For candidate M0 (`beta_M=0`):
- N0 `NULL_CLEAN`: true beta=0, no latent confounder, sigma=1.0.
- N1 `NULL_LATENT_CONFOUNDING`: beta=0, gamma=1.2, sigma=0.7.
- N2 `NULL_ALEATORIC`: beta=0, gamma=0, sigma=2.0.
- N3 `NULL_MIXED_NUISANCE`: beta=0, h=0.5, gamma=1.0, sigma=0.8.
- S1 `MISSING_TRUE_EDGE`: beta=+0.8, gamma=0.8, sigma=0.7.
- S2 `MISSING_TRUE_EDGE_NEGATIVE`: beta=-0.8, gamma=0.8, sigma=0.7.
- W1 `WEAK_EDGE_BUDGET_STRESS`: beta=+0.15, gamma=0.8, sigma=0.7; failure to reject is not a scientific failure.

For candidate M+ (`beta_M=+0.8`):
- S3 `SPURIOUS_CANDIDATE_EDGE`: true beta=0, gamma=0.8, sigma=0.7.

Equivalence control E0: only one intervention level `do(X=+1)` is exposed with true beta=+0.7, so the frozen nuisance intercept range [-0.75,+0.75] can exactly absorb the apparent slope difference. Its exact profiled KL must be zero to numerical tolerance and the instrument must return `UNRESOLVED_INTERVENTIONAL_EQUIVALENCE`, not causal acceptance or graph falsification.

Out-of-envelope O1: correct slope but SD outside the declared envelope. Any rejection must be labeled `MODEL_CLASS_FALSIFIED_NUISANCE_ATTRIBUTION_UNRESOLVED`, never topology-specific.

## Cohorts

- design pilot: seeds 41000..41063, non-authoritative;
- PRIMARY: 128 fresh seeds/family from 61000 with deterministic family offsets;
- REPLICATION: 128 fresh seeds/family from 71000 with deterministic family offsets.

No confirmatory seed may occur in the pilot.

## Primary metrics and gates

PRIMARY and REPLICATION independently require:
1. in-envelope null false-rejection rate <=0.01 pooled and zero family above 0.02;
2. S1, S2, S3 rejection rate >=0.95 within cost 256;
3. E0 separation rate = 0 (tol 1e-12) and false rejection count = 0;
4. no topology-specific verdict for O1;
5. hidden-confounder vs aleatoric variance decomposition reproduced as non-identifiable (multiple gamma,sigma pairs yield exactly the same total interventional variance);
6. intervention-cost accounting exact and no sample after rejection;
7. no active inference/replay/weight/logit authority.

If PRIMARY fails, REPLICATION cannot rescue the claim.

## Interpretation

PASS means: under the declared finite Gaussian nuisance class and controlled interventions, the instrument can falsify some causal model classes with anytime-valid type-I control and can correctly declare non-identifiability when intervention support is insufficient.

PASS does **not** mean latent confounding is solved, the true graph is identified, `phi_*` is known, arbitrary world-model misspecification is detected, or real-model inference is promoted.
