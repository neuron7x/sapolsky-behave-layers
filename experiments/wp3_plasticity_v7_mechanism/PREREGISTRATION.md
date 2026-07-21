# PREREGISTRATION — L4e Mechanism Model (why the collapse scales the way it does)

**Committed before the run.** L4c/L4d found the governor's collapse margin scales with the
budget as `Δ* ∝ N^−0.654` (STEEPER than the `−0.5` sample-complexity law) and that noise
HELPS (`Δ*(2σ)/Δ*(σ) < 1`). This tests an explicit mechanistic account.

## The proposed mechanism (derived, then tested by ablation)

For a REINFORCE softmax policy the expected logit-gap drift between the best arm `b` and its
runner-up `r` is `dg/dt ∝ LR · Δ · π_b(1−π_b)` (standard policy-gradient of the expected
reward w.r.t. the logit gap). Two consequences:

1. **Steeper-than-√N budget scaling.** The drift is *proportional to Δ* and grows as the
   policy separates, so resolution is faster than pure `(σ/Δ)²` estimation (diffusion-limited
   `−0.5`) and approaches the drift-limited `Δ* ∝ 1/N` (`−1`). The observed `−0.654` sits
   between — a drift-assisted regime, not pure estimation.
2. **Noise-as-exploration.** With a moving-average baseline the update is
   `LR·(R−baseline)·∇log π`; larger reward noise `σ` inflates `|advantage|`, so bigger updates
   escape the `π≈0.5` saddle and premature commitment to `r` — noise HELPS, giving
   `Δ*(2σ)/Δ*(σ) < 1`, the opposite of the estimation law.

**Falsifiable claim:** this is a **two-arm** phenomenon — the two clearly-dominated arms and
the 4-arm structure are irrelevant. So an **ablation to 2 arms** (`b` vs `r` only, same
REINFORCE) must reproduce BOTH signatures of the full 4-arm governor.

## Design (frozen)

- **Reduced model:** identical governor and sweeps as L4d, but `N_ARMS = 2` (drop the two
  dead arms). 24 controller seeds, extended `Δ` grid, budget sweep `N ∈ {1500,3000,6000,
  12000}` at `σ=0.10`, and `σ ∈ {0.10, 0.20}` at `N=3000`. Same `Δ*` estimator.
- **Full-governor targets (frozen, from committed L4d `artifacts/wp3-plasticity-v6-scaling/`):**
  budget exponent `−0.654`; noise ratio `0.500 < 1`.

## Decision rule (FROZEN)

- **L4E_MECHANISM_EXPLAINED** iff the 2-arm reduction reproduces the full governor:
  (1) reduced budget exponent (log-log slope of `Δ*` vs `N`) within `±0.15` of `−0.654`;
  (2) reduced noise ratio `Δ*(2σ)/Δ*(σ) < 1.0` (noise helps, same sign).
- **L4E_MECHANISM_INCOMPLETE** — either signature is not reproduced by the 2-arm reduction
  (the 4-arm / baseline structure matters; the simple account is insufficient).
- **L4E_INSTRUMENT_LIMITED** — residual off-grid `NaN` in the reduced `Δ*` (extend grid).

## AMENDMENT 2026-07-21 (disclosed — instrument-range, and a magnitude finding seen)

First run (prereg `68aaccc`) showed the 2-arm reduction is FAR more sample-efficient than the
full governor: reduced `Δ*(1500)=0.0140` vs full `0.0567` (~4× smaller), and reduced
`Δ*(12000)` fell below the 0.005 grid floor → `NaN` → `INSTRUMENT_LIMITED`. Disclosed: this
already indicates the two dead arms MATTER (suppressing them in the 4-arm softmax dilutes the
b-vs-r mass and enlarges `Δ*`), so the budget MAGNITUDE is not a pure 2-arm effect; the noise
ratio (0.357) did reproduce `< 1`. Per `PROTOCOL_AMENDMENT_AND_DEVIATION_POLICY`, extend the
grid downward with finer low-`Δ` resolution to `Δ ∈ {…,0.02,0.015,0.01,0.008,0.005,0.003,
0.001}` so the reduced exponent is measurable. Thresholds unchanged; the magnitude mismatch is
reported regardless of the exponent outcome.

## Scope / prohibited

Tier `SYNTHETIC-PARAMETRIC`. A mechanistic explanation of the governor's collapse scaling,
not a capability claim. New claim `CWC-L4e-mechanism`. Does not establish real-workload
behavior, L7, energy/latency, or independent replication.
