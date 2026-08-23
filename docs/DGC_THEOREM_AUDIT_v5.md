# DGC Theorem Audit v5

Status: `PRE_EXECUTION_THEOREM_TRANSCRIPTION_AUDIT`.

This document audits the mathematical mapping used by DGC product-evidence protocol V5. It is not empirical evidence that DGC passes the protocol.

## Primary source

Steven R. Howard, Aaditya Ramdas, Jon McAuliffe, Jasjeet Sekhon, *Time-uniform, nonparametric, nonasymptotic confidence sequences*, Annals of Statistics 49(2), 2021; arXiv:1810.08240.

DGC uses the paper's empirical-Bernstein confidence-sequence construction: Theorem 4 composed with the polynomial-stitching uniform boundary of Eq. (10).

Author reference implementation used for independent transcription checking:

- repository: `gostevehoward/confseq`;
- commit: `5ffe733ca2447a2e28c2c91f3b00086173f2ab2c`;
- implementation: `PolyStitchingBound::operator()`;
- author test vector: `poly_stitching_bound(100, 0.05, 10, 3) = 64.48755 ± 1e-5`.

## DGC estimand

For the precommitted ordered bounded sequence `X_1,...,X_t`, DGC targets

`mu_bar_t = (1/t) * sum_i E[X_i | F_{i-1}]`.

This is an average conditional mean. It is not silently reinterpreted as an iid population mean, a universal task-distribution mean or a production-wide causal effect.

## Predictable center

After affine rescaling to `[0,1]`, DGC freezes

`Xhat_t = (1/2 + sum_{j<t} X_j) / t`.

The center depends only on observations before `t`, is therefore predictable with respect to `F_{t-1}`, and lies in `[0,1]`. The empirical variance process is

`V_t = sum_i (X_i - Xhat_i)^2`.

Predictor identity: `BETA_HALF_SMOOTHED_PREVISIBLE_MEAN_V1`.

## Exact polynomial-stitching boundary

For `v >= 0`, `v_min > 0`, scale `c`, `eta=2`, `s=1.4`, define

`use_v = max(v, v_min)`

`ell = s*log(log(eta*use_v/v_min)) + log(zeta(s)/(alpha_boundary*log(eta)^s))`

`k1 = (eta^(1/4) + eta^(-1/4))/sqrt(2)`

`k2 = (sqrt(eta)+1)/2`

`term2 = k2*c*ell`

and

`u(v) = sqrt(k1^2*use_v*ell + term2^2) + term2`.

This is the formula implemented by the authors' `PolyStitchingBound` and used by V5.

## Two-sided error allocation

Theorem 4 gives a two-sided confidence sequence with coverage at least `1 - 2*alpha_boundary` when `u` has one-boundary crossing probability `alpha_boundary`.

Therefore, if the DGC per-claim two-sided error budget is `delta`, V5 freezes

`alpha_boundary = delta / 2`.

For the primary two-family / four-baseline / three-endpoint familywise allocation:

`delta = 0.05 / (2*4*3) = 0.05/24`.

Hence the polynomial-boundary crossing probability for one primary endpoint comparison is

`alpha_boundary = 0.05/48`.

For G1-G5, the generalization family remains separately Bonferroni-controlled across `5*4*3 = 60` claims before applying the same two-sided halving inside Theorem 4.

## V4 defect and V5 correction

V4 used

`k1*sqrt(v*ell) + k2*c*ell`.

That expression omits `term2^2` inside the canonical square root. It can be narrower than the authors' polynomial-stitching boundary and therefore is not accepted as a theorem-valid substitute.

V5 replaces the shortcut with the exact author formula. V4 was frozen before external confirmatory outcomes, archived, and superseded before any product-evidence execution.

## Machine falsifiers

The V5 test surface must kill at least these mutations:

1. remove `term2^2` from the canonical square root;
2. omit the final `+term2`;
3. use `delta` instead of `delta/2` for the Theorem-4 crossing probability;
4. change `eta`, `s` or frozen `zeta(1.4)` silently;
5. allow a non-predictable center that consumes `X_t` before predicting `X_t`;
6. violate observation support;
7. change analysis order after outcomes;
8. substitute an iid/population-mean claim for the average-conditional-mean estimand.

## Limits

This theorem audit establishes only the intended mathematical transcription and claim boundary. It does not establish that the current branch executes successfully, that external benchmark observations satisfy the inequalities, that workload scorers are causally sufficient, or that the observed effect generalizes beyond the explicitly tested shift panels.
