# CSCA-07 — Passive Replay Identifiability Theory

## Scope

This note states the exact epistemic boundary for causal abstractions learned or invented during offline generative replay when no new environment intervention is available. It separates three questions:

1. Is the replay model's **observable predictive law** wrong?
2. Is a latent representation **internally stable/compressed**?
3. Is the latent representation the **environment's causal abstraction**?

Only (1) is universally testable from passive factual data without extra assumptions. (2) is an internal property. (3) requires identifiability.

## Theorem 1 — observational-equivalence veto

Let `M in {0,1}` index two candidate latent models with prior `pi(M)>0`, and let `D_n` be any finite passive factual trace. If

`P(D_n | M=0) = P(D_n | M=1)`

for every measurable trace event and every `n`, then

`I(M;D_n)=0`.

Moreover, for any passive test `T(D_n) in {0,1}`, if

`P_0(T=1) <= alpha`,

then

`P_1(T=1) <= alpha`.

### Proof

Equality of trace laws makes the likelihood ratio identically one. Bayes' rule therefore leaves the posterior over `M` equal to its prior, giving `I(M;D_n)=0`. Since `T` is a measurable function of `D_n`, its distribution is also identical under both models. Hence its rejection probability under model 1 equals its type-I rejection probability under model 0. QED.

### Consequence

No amount of replay compute changes this. If the factual channel contains zero information about which causal model is true, internal simulation only processes information already present in that channel plus assumptions encoded by the model.

## Theorem 2 — passive information/cost converse

Let `A` be the event that a level-alpha passive test rejects a declared predictive model. Suppose under an alternative factual law the desired rejection probability is at least `p > alpha`. By data processing of KL divergence through the binary map `D -> 1_A`,

`D_KL(P_* || P_M) >= kl(p || alpha)`.

If factual evidence accumulates at at most `R` nats per unit acquisition cost, then a necessary condition is

`Cost >= kl(p || alpha) / R`.

This is **necessary, not sufficient**.

When `R=0`, the required cost is infinite. This is the mathematical form of observational equivalence.

At the CSCA-07 frozen values `alpha=.01`, `p=.95`, the required information is

`kl(.95 || .01) = 4.176898950135489 nats`.

## Proposition 3 — Jacobian spectrum is not a universal causal identifier

For a linear latent system `z_{t+1}=A z_t+w_t`, choose any invertible `T` and define

`z'_t=T z_t`, `A'=T A T^{-1}`, `C'=C T^{-1}`, `w'_t=T w_t`.

Then the observable path `x_t=Cz_t=C'z'_t` is identical, and `A` and `A'` have identical eigenvalues because they are similar matrices. Yet the zero/non-zero pattern of `A'` can differ from that of `A`.

Therefore spectral properties of `nabla_z F` may diagnose local dynamics but cannot, by themselves, identify latent causal topology.

CSCA-07 instantiates this exactly: spectral distance `5.55e-17`, maximum path error `4.44e-16`, different adjacency.

## Proposition 4 — stable invariant replay fixed point is not external causal evidence

A hidden replay coordinate can satisfy a contracting fixed-point equation while being absent from the observation map. CSCA-07 constructs one with local spectral radius `0.1383`, zero context derivative, and zero observational information about the hidden state.

Thus

`rho(nabla F)<1`

can certify local contraction of the replay dynamics but not correspondence to an environment variable.

## Proposition 5 — within-model fiber entropy is insufficient

Let model index `M` and observed bit `X` be independent. Define `Z=X` for `M=0` and `Z=1-X` for `M=1`. Then

`H(Z|X,M)=0`

inside every candidate model, but

`I(M;X)=0`.

So perfect within-model compression/invertibility does not choose the correct latent semantics. The relevant unresolved uncertainty lives across the observational-equivalence class of models.

## Engineering authority rule

Passive data may produce only:

- `REJECT_REPLAY_PREDICTIVE_LAW` when the observable law is falsified;
- `PASSIVE_EQUIVALENCE_UNRESOLVED_CAUSAL_AUTHORITY_BLOCKED` when the observable law survives but causal identification is unavailable;
- `CAUSAL_CANDIDATE_UNDER_EXPLICIT_IDENTIFYING_ASSUMPTIONS` only when those assumptions are separately declared, testable where possible, and bound to the verdict.

`TRUE_CAUSAL_ABSTRACTION` is not an admissible passive-only machine verdict.

## What can break the impossibility boundary

Additional structure can make observational causal identification possible in restricted model classes. Examples include explicitly justified assumptions about observation grouping, independent mechanisms/spectral independence in restricted linear systems, temporal/noise asymmetry, valid instruments, or known exogenous regime variation. These are assumptions or extra information channels, not consequences of replay self-consistency. Each requires its own preregistered falsification gate.
