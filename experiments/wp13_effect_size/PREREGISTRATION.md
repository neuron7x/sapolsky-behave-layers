# PREREGISTRATION — WP13 Effect Sizes, Bootstrap CIs, Retrospective Power

**Committed before the run.** Beyond the one-sided `G_lo > 0` gate, an expert expects effect sizes
with uncertainty and a power statement. This reports, for each certificate positive, a seed-bootstrap
95% CI of the oracle gap, a standardized effect (`gap/σ`), and the sample-complexity `n*`.

## Design (frozen)

For `CWC-L4-plasticity` (16 seeds) and `CWC-AC1-compute` (8 seeds): oracle gap `Ĝ`; seed-bootstrap
(2000 resamples, seeded) 95% percentile CI; `σ_max`; standardized effect; `n* =
sample_complexity(Ĝ, σ, |C|, |A|, δ=0.05)` and whether `n_seeds ≥ n*`.

## Decision rule (FROZEN)

- **EFFECT_SIZES_CI_POSITIVE** iff both positives' bootstrap 95% CI **lower bound > 0** (the effect
  is robustly positive by bootstrap, complementing the analytic certificate).
- **EFFECT_SIZE_CI_CROSSES_ZERO** — a CI includes 0 (honest: the effect is not bootstrap-robust).

## Scope

Meta / statistical reporting. New claim `CWC-RIGOR6-effect-size`.
