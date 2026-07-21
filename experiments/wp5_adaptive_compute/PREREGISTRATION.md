# PREREGISTRATION — WP5 Adaptive-Compute Identifiability (a second real mechanism)

**Committed before the confirmatory run.** The L4 line established the identifiability framework
on the *parameter-plasticity* axis (which group to adapt). This tests whether it **transfers to a
different real mechanism — adaptive COMPUTE** (how many iterations to spend), the axis directly
relevant to L7. If the framework is mechanism-specific, it fails here.

## Mechanism (real, trainable)

A weight-tied recurrent transformer block; one iteration = a clean shift-by-1 operator, so `K`
iterations compute a shift-by-`K`. Task: `shift-by-d` (`y_i = x_{i-d}`), difficulty `d ∈ {1,2,3}`.
A shift-by-d answer needs exactly `d` iterations — **more compute overshoots and HURTS**. So the
context is difficulty `d`, the action is the compute budget `K ∈ {1,2,3}`, and
`acc[d][K] ≈ 1` iff `K = d` (a diagonal, verified in a scouting probe: off-diagonal ≈ 0.06).

## Design (frozen)

- Fresh held-out seeds `0..7` (8 seeds). Train 1500 steps/seed (`~6 s`), eval `acc[d][K]` on 1024
  inputs. Written to `artifacts/wp5-adaptive-compute-identifiability/raw_runs`.
- Compute-budget utility `U_λ[d][K] = acc[d][K] − λ · K/3`, `λ ∈ {0.0, 0.5, 1.0}`.
- Certificate `G_lo` (`identifiability_inference`, δ=0.05, se over the 8 seeds), contexts=depths,
  actions=K.

## Predictions (frozen)

1. **Identifiable even unbudgeted:** because overshoot hurts, the oracle (`K=d` per difficulty)
   beats the best fixed `K` at `λ=0` already ⇒ `G_lo > 0` at every `λ`.
2. **Diagonal mechanism:** worst-seed diagonal accuracy `acc[d][d] ≥ 0.9`; worst off-diagonal
   `≤ 0.3`.

## Controls (mandatory)

- **MONOTONE-COMPUTE null:** replace `acc` by its cumulative max `acc*[d][K] = max_{k≤K} acc[d][k]`
  (more compute never hurts). Then fixed `K=3` solves everything ⇒ oracle gap must vanish
  (`G_lo ≤ 0` at `λ=0`). This isolates that the value comes from *overshoot*, i.e. real
  compute-allocation, not a labeling artifact.
- **ADDITIVE null:** additive ANOVA reconstruction of `U` (no interaction) ⇒ `G_lo ≤ 0`.

## Decision rule (FROZEN)

- **AC1_IDENTIFIABLE** iff the diagonal holds (pred 2), `G_lo > 0` at every `λ` (pred 1), AND both
  nulls vanish (`G_lo ≤ 0`). The identifiability framework transfers to the compute mechanism.
- **AC1_NOT_IDENTIFIABLE** — `G_lo ≤ 0` at some `λ` (no allocation value on this mechanism).
- **AC1_VOID** — a null shows a gap, or the diagonal fails (mechanism/instrument broken).

## Scope / prohibited

Tier `SYNTHETIC` (real trainable model, synthetic shift task). Establishes that adaptive-compute
allocation is identifiable — a second mechanism for the framework. New claim
`CWC-AC1-compute-identifiability`. Does NOT establish: a learned compute-controller (a follow-up),
real-workload, compute-equivalent Pareto (L7), or independent replication.
