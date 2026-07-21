# WP5 Adaptive-Compute Identifiability — RESULTS (a second real mechanism)

**Verdict: `AC1_IDENTIFIABLE`.** Preregistration:
`experiments/wp5_adaptive_compute/PREREGISTRATION.md`. Reproduce:
```
PYTHONPATH=. python -m experiments.wp5_adaptive_compute.src.runner_oracle --seeds 0..7
PYTHONPATH=. python -m experiments.wp5_adaptive_compute.src.analyze
```

## The identifiability framework transfers off parameter-plasticity onto adaptive COMPUTE

A weight-tied recurrent transformer where one Block iteration is a clean shift-by-1 operator, so
`K` iterations compute a shift-by-`K`. The task `shift-by-d` (`d ∈ {1,2,3}`) needs exactly `d`
iterations — a real, trained diagonal (worst on-diagonal `acc[d][d]=0.998`, worst off-diagonal
`0.068` across 8 seeds): more compute **overshoots and hurts**.

| `λ` (compute cost) | real `G_lo` | monotone-compute null | additive null |
|---|---|---|---|
| 0.0 | **+0.621** | −0.002 (vanishes) | −0.002 (vanishes) |
| 0.5 | **+0.455** | +0.164 | −0.002 |
| 1.0 | **+0.289** | +0.289 | −0.002 |

The oracle compute-allocation (`K=d` per difficulty) is **identifiable at every `λ`** (`G_lo>0`),
and both nulls vanish at `λ=0`. Adaptive-compute allocation is a genuine, learnable-value
mechanism — the identifiability framework is **not specific to plasticity**.

## Two sources of identifiability (a distinction plasticity lacked)

- **Overshoot** (`λ=0`): more compute *hurts* (K>d overshoots the shift), so the oracle beats any
  fixed `K` even at zero cost — hence real `G_lo=0.621` at `λ=0` while both nulls sit at 0.
- **Budget** (`λ>0`): compute costs, so allocating less to easy inputs pays — this is the classic
  cost-budget value, and it is why the *monotone-compute* null (where overshoot is removed) still
  shows a gap at `λ>0` (`+0.164, +0.289`). That is expected and correct — under a compute budget,
  spending less on easy inputs has value even when more compute never hurts. The null is checked at
  `λ=0` (where it correctly vanishes), isolating the overshoot source.

Plasticity had only the budget source; the compute mechanism has both, making it **more robustly
identifiable**.

## Consequence for the claim ladder

`CWC-AC1-compute-identifiability` is registered **SUPPORTED**: adaptive-compute allocation is
identifiable on a second real mechanism. This is the axis L7 targets. Frozen. It does NOT yet show
a *learned* compute-controller (a follow-up), a real workload, or the compute-equivalent Pareto
(L7).

## Scope

Tier `SYNTHETIC` (real trainable recurrent model, synthetic shift task).
