# CSCA-05 PRE-EXECUTION AMENDMENT 001 — Intervention semantics and Shapley estimator

**Status:** frozen before any CSCA-05 model training, calibration, primary, or replication result.

Analytic review found a semantic mismatch in the initial preregistration: the existing `ANTITHETIC_CRN_MC` estimator from CSCA-03R assumes a symmetric random {-1,+1} resampling baseline. CSCA-05 defines a **deterministic physical intervention**: `do(span = ASCII_SPACE)`. Importing the resampling estimator unchanged would alter the estimand.

Therefore CSCA-05 uses a separately named deterministic-ablation Shapley family:

- `EXACT_ABLATION_SHAPLEY`: standard Shapley over the 2^4 keep/ablate coalitions;
- `ANTITHETIC_PERMUTATION_ABLATION_SHAPLEY`: permutation paths paired with reverse permutations, with coalition-result caching.

The causal outcome, candidate spans, data splits, delta rule, authority rule, and qualification thresholds are unchanged.

The calibration budget grid is changed **before execution** to `[1, 2, 4, 8]` antithetic permutation pairs. `pairs=1` is permitted for accuracy diagnostics but cannot issue authority because sampling variance is not estimable from one pair. The smallest authority-bearing budget therefore remains at least two pairs.

Physical cost is reported as both logical coalition evaluations and unique actual model forward passes. Exact enumeration is expected to remain competitive at four candidates; no runtime-compute advantage claim is allowed from this pilot.
