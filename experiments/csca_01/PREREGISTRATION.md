# CSCA-01 — Counterfactual Credit Kernel Reproduction & Falsification

**Status:** FROZEN BEFORE EXECUTION  
**Authority target:** mechanism-level synthetic reproduction only; never paper-level reproduction or architecture integration.

## Hypothesis

In a known SCM with one delayed manipulable cause `A`, temporally adjacent and correlated non-causes `B/C`, random distractor `D`, latent confounding `U`, and delayed outcome `Y`, exact counterfactual Shapley credit should uniquely rank `A` above non-causes under IID and OOD context shifts while assigning zero structural credit to non-causes.

A finite-budget Monte-Carlo permutation estimator is a separate computational approximation. Its performance is measured, not assumed.

## Structural environment

`Y = beta*A + gamma(context)*U + epsilon`.

`C` is a noisy readout of `U`; `B` is temporally adjacent and observationally associated with `A`; `D` is random. `C/B/D` are absent from the structural outcome equation.

Candidate intervention baseline resamples selected candidate variables independently from `{-1,+1}` while reusing the row's exogenous `U, epsilon`.

## Frozen cohorts

- PRIMARY: seeds `12000..12031`
- INDEPENDENT_REPLICATION: seeds `22000..22031`
- 128 trajectories per context per seed
- contexts: `TRAIN_CONFOUNDED`, `OOD_WEAK_CONFOUNDER`, `OOD_SIGN_INVERSION`

Primary and replication runs must execute from the same committed implementation.

## Methods

- `EXACT_CF_SHAPLEY`
- `MC_CF_SHAPLEY_4`
- `MC_CF_SHAPLEY_16`
- `MC_CF_SHAPLEY_64`
- `OBS_ASSOC`
- `RECENCY`
- `TD_ELIGIBILITY_PROXY` (explicitly not canonical TD)
- `UNIFORM`
- `RANDOM`

## Primary metric

`causal_rank_accuracy`: fraction of independent seed×context units where `A` has strictly larger absolute credit than each non-cause.

Secondary:

- normalized false-credit mass;
- exact Shapley efficiency error;
- Monte-Carlo structural evaluation count;
- wall time.

## Primary predicates

`EXACT_CF_SHAPLEY` must satisfy all:

1. OOD causal-rank accuracy = `1.0` in PRIMARY;
2. OOD causal-rank accuracy = `1.0` in INDEPENDENT_REPLICATION;
3. mean OOD false-credit mass <= `1e-12` in both cohorts;
4. maximum exact Shapley efficiency error <= `1e-12`;
5. `DESTROY_CAUSAL_LINK`, `CORRELATION_ONLY`, and `PURE_NOISE` exact-credit nulls have maximum absolute candidate credit <= `1e-12`.

Approximation qualifier (`MC_CF_SHAPLEY_64`) is secondary and requires OOD causal-rank accuracy >= `0.95` in each cohort. Failure does not falsify exact Shapley; it falsifies the chosen finite-budget approximation.

## Nulls

- N1 `DESTROY_CAUSAL_LINK`
- N2 `CORRELATION_ONLY`
- N3 `PURE_NOISE`
- N4 `HIGH_NOISE`
- N5 OOD context sign inversion (part of primary contexts)

## Failure predicate

Any failed exact primary predicate => `CSCA_01_EXACT_KERNEL_NOT_REPRODUCED`.

If exact passes but MC64 fails => `CSCA_01_EXACT_REPRODUCED_APPROXIMATION_NOT_QUALIFIED`.

If exact and MC64 pass => `CSCA_01_CONTROLLED_KERNEL_REPRODUCED`.

No outcome in this experiment grants architecture promotion. Full primary-source bytes and paper code are not materialized in the current environment; therefore the strongest possible claim is an independent controlled mechanism reproduction of the formalized kernel.
