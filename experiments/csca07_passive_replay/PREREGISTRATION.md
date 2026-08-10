# CSCA-07-PR — Passive Replay Identifiability & Hallucination Boundary

**STATUS:** FROZEN BEFORE CONFIRMATORY EXECUTION
**MODE:** PASSIVE-TRACE ONLY · NO NEW ENVIRONMENT INTERVENTIONS · FAIL-CLOSED

## Kill question
Can a stable, internally invariant replay abstraction be certified as an environment-causal abstraction from `D_fact` alone?

## P0 theorem target — observational-equivalence veto
For latent-model index `M`, if two candidate models induce the same law on every factual trace,
`P(D_fact|M=0)=P(D_fact|M=1)`, then `I(M;D_fact)=0`; no passive statistic can distinguish the models.
This includes statistics computed from a candidate model itself unless their relation to the environment is separately identifiable.

## P1 spectral attack
Construct two linearly similar latent dynamical realizations with:
- exactly the same observable sample path under transformed initial state/noise;
- identical eigenvalues of the latent Jacobian;
- different directed sparsity/topology of the latent transition matrix.

Failure predicate for spectral sufficiency: if all three hold, `JACOBIAN_SPECTRUM_CAUSAL_SUFFICIENCY = KILLED`.

## P2 autocatalytic fixed-point attack
Append an unobserved replay coordinate with a stable predicate-supported fixed point, local spectral radius `<1`, and exact context invariance, while the observation law is unchanged.
If this construction succeeds, internal stability + invariance is not sufficient evidence of environment causality.

## P3 fiber-entropy attack
Discrete construction: `M` and factual bit `X` independent; candidate 0 defines `Z=X`, candidate 1 defines `Z=1-X`.
Each candidate has `H(Z|X,M)=0`, while `I(M;X)=0` and the cross-model fiber ambiguity is 1 bit.
Failure predicate: zero within-model fiber entropy must not grant causal authority.

## P4 passive falsifier
Use an anytime-valid likelihood-ratio e-process:
- null = declared Gaussian AR(1) transition law;
- numerator = predictable Bayesian mixture of predeclared AR(1) alternatives;
- reject observational law at `e >= 1/alpha`.

`alpha = 0.01`. This may reject the candidate predictive law only; never the latent graph.

## P5 confirmatory families
Fresh cohorts: PRIMARY 128 seeds/family and independent REPLICATION 128 seeds/family; 256 transitions/trace. Seed blocks are disjoint between cohorts. Thus each family has 256 confirmatory traces total.

- `N0_TRUE_OBSERVED_LAW`: true a=.75, candidate a=.75. Required rejection rate <= .02.
- `S1_WRONG_DYNAMICS`: true a=.75, candidate a=.25. Required rejection rate >= .95.
- `S2_WRONG_SIGN`: true a=.75, candidate a=-.40. Required rejection rate >= .95.
- `W1_WEAK_MISSPECIFICATION`: true a=.75, candidate a=.68. No power threshold; information converse decides whether 256 transitions can support target power .95.
- `E0_EQUIVALENT_LATENT_TOPOLOGY`: observational law identical; topology disambiguation must remain blocked.
- `H0_HIDDEN_AUTOCATALYTIC`: observational law identical despite stable hidden replay fixed point; causal promotion must remain blocked.

Alternative mixture coefficients are frozen at `[-.75,-.4,0,.25,.5,.68,.75,.9]`, common innovation sd `.5`.

## P6 information-cost converse
For level `alpha` and target power `p`, data processing gives the necessary condition
`D(P*||P_M) >= kl(p||alpha)` for the rejection event. With stationary information rate `R` nats/transition,
`n >= kl(p||alpha)/R` is necessary, not sufficient. If `R=0`, required passive sample cost is infinite.

## P7 authority rule
Possible outputs:
- `REJECT_REPLAY_PREDICTIVE_LAW`
- `PASSIVE_EQUIVALENCE_UNRESOLVED_CAUSAL_AUTHORITY_BLOCKED`
- `CAUSAL_CANDIDATE_UNDER_EXPLICIT_IDENTIFYING_ASSUMPTIONS`

This experiment cannot emit `TRUE_CAUSAL_ABSTRACTION`, `SHADOW_CAUSAL_PROMOTION`, `REPLAY_CONTROL`, or `ACTIVE_CONTROL`.
