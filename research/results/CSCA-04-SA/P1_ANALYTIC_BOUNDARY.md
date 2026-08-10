# CSCA-04-SA — P1 Analytic Identifiability Boundary

## Constructive counterexample

Let the observational support satisfy `C=A` exactly and consider two deterministic models:

- `M_true: Y=A`
- `M_alt:  Y=C`

For every observational sample on the support `C=A`,

`M_true(x) = M_alt(x)`.

Therefore any statistic that is a function only of factual predictions/residuals on that support — factual RMSE, likelihood, calibration, ensemble agreement over observationally equivalent models — can be identical under both models.

Under intervention `do(C=-A)` while holding `A` fixed:

- `M_true` predicts no effect of changing `C`;
- `M_alt` predicts a non-zero effect.

Thus factual equivalence does not imply interventional equivalence. A structural-adequacy certificate requires intervention information or assumptions strong enough to identify the intervention distribution.

## Consequence for GSS

Internal graph/term ablation measures model reliance, not truth. In the same collinear support, a model may rely strongly on `C` while `C` is not a true cause. Therefore GSS can be a useful fragility diagnostic but cannot independently authorize causal credit.

## Operational implication

The primary structural gate must compare environment response under explicit interventions with model-predicted intervention response. Observational metrics remain secondary diagnostics.
