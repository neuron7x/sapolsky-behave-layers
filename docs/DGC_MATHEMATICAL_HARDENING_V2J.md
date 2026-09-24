# DGC Mathematical Hardening v2j — Ratio-Free Finite-Strata Transport

Date: 2026-08-23

## Proposition P32

Let `(Z_i,Y_i)` be iid source observations with `Y_i in [L,H]`. Let `Z'_j` be iid target covariates independent of the source sample. Assume a declared finite stratum partition and externally attested conditional-mean invariance

`E_P[Y | Z=z] = E_Q[Y | Z=z]`

for every target-observed stratum. Also require observed support overlap: each stratum appearing in the target sample must have at least one labeled source observation.

For total error probability `delta`, split `delta/2` to source conditional-mean estimation and `delta/2` to target-mixture sampling. For `m` target-observed strata, construct simultaneous one-sided Hoeffding lower bounds

`l_z = max(L, mean_z - (H-L)*sqrt(log(m/(delta/2))/(2 n_z)))`.

By Bonferroni, with probability at least `1-delta/2`, all `l_z <= E_P[Y|Z=z] = E_Q[Y|Z=z]` simultaneously. Conditional on that source event, define `g(z)=l_z`. On the independent target sample, one-sided Hoeffding gives

`E_Q[g(Z)] >= mean_j g(Z'_j) - (H-L)*sqrt(log(1/(delta/2))/(2 n_target))`

with probability at least `1-delta/2`. Since `g(z) <= E_Q[Y|Z=z]`, we have `E_Q[g(Z)] <= E_Q[Y]`. A union bound therefore yields a target-mean lower confidence bound with confidence at least `1-delta`.

## Why this closes a real gap

The previous covariate-shift path required an externally authoritative density ratio or an externally supplied ratio-error budget. v2j adds a separate restricted path that does not estimate `dQ/dP` at all. For auditable discrete workload strata, target mixture proportions are learned directly from the independent target covariate sample while outcome information comes only from labeled source strata.

This is useful for deployment strata such as workload family, difficulty bucket, tool topology, task class or other preregistered categorical partitions where conditional-mean transport is defensible and independently auditable.

## Validity boundary

The result is deliberately narrow. It is invalid when:

- the stratum partition is selected after looking at outcomes;
- target-only strata are silently smoothed or extrapolated;
- conditional-mean invariance is false;
- source and target samples are dependent in a way that breaks the conditional argument;
- covariates are continuous without a frozen finite partition;
- the target population changes after the target sample is collected.

An attestation is not empirical proof that invariance is true; it is an explicit causal/statistical obligation. External qualification must validate that obligation independently.

## Prior-art boundary

This construction is a finite-strata standardization / transport argument using Hoeffding concentration and Bonferroni control. DGC claims no novelty for covariate-shift standardization, importance weighting, or transportability theory. The contribution here is engineering the theorem as a fail-closed, hash-bound control-plane primitive and keeping its authority separate from broader client/product claims.

Relevant contemporary context includes weighted conformal/risk-control methods under covariate shift and recent work emphasizing that density-ratio estimation can be fragile or inefficient under complex shift. Those works motivate the need for a restricted ratio-free path but do not make this DGC implementation externally validated.

## Executable falsification

- `tests/test_dgc_math_v2j.py`: 7 targeted tests.
- `scripts/dgc_math_v2j_attack.py`: kills two unsafe mutations:
  - reusing the source mixture instead of the observed target mixture;
  - smoothing an unseen target stratum instead of failing positivity.

Local targeted result before commit: `7 passed`; attack gate `PASS`.

## Promotion consequence

This improves the mathematical coverage of restricted distribution transport, but it does not justify `PRODUCT_QUALIFIED`, `CLIENT_VERIFIED`, or a >=90% mathematics score by itself. Continuous/high-dimensional shift, conditional shift, external invariance validation and real client-distribution calibration remain open.
