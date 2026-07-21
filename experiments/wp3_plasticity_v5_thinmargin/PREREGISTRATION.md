# PREREGISTRATION — L4c Thin-Margin Credit-Assignment Collapse

**Committed before the run.** L4a/L4b ran on WIDE reward margins, so the governor
trivially learned. This stress test isolates the *distinguishability* of the best arm from
its runner-up (margin `Δ`) at a fixed learning budget, and finds where the governor's
REINFORCE credit assignment **collapses** — the failure mode that sank routing R3-C. The
collapse boundary is predicted from the sample-complexity law and the prediction is tested.

## Design (frozen)

- **Parametric contextual bandit** (tier SYNTHETIC-PARAMETRIC — this characterizes the
  GOVERNOR mechanism's limit, not the plasticity benchmark). 2 contexts, 4 arms. Per
  context the best arm pays mean `1.0`, its runner-up `1.0 − Δ`, the other two `0.0`.
  Context 0's best is arm 0; context 1's best is arm 1 (so context-conditioning matters and
  the two top arms swap). Reward noise `~ N(0, σ²)` per pull.
- `oracle = 1.0`; `best_fixed = 1.0 − Δ/2`; `gap = Δ/2`.
  `recovery = (realised − best_fixed) / (gap)`; perfect routing → 1, guessing between the
  top two → 0.
- **Governor:** the SAME REINFORCE softmax `π(arm | context)` as L4a, **fixed** episode
  budget `N_EPISODES` (no budget growth as Δ shrinks — that is the stress).
- **Sweep:** margin `Δ ∈ {0.40, 0.20, 0.10, 0.05, 0.02}` at TWO noise levels
  `σ ∈ {σ0, 2·σ0}` with `σ0 = 0.10` (calibrated to the measured plasticity reward scale).
  8 controller seeds per cell; report the mean recovery.

## Grounded prediction (sample-complexity law, NOT fit)

Distinguishing two arms with mean gap `Δ` and per-pull noise `σ` from `n` pulls needs
`n ≳ (σ/Δ)²` (the same `n* = ⌈(σK/G)²⌉` scaling as the certificate). At a FIXED episode
budget the effective pulls per (context, arm) is fixed, so the governor identifies the best
arm iff `Δ ≳ Δ*(σ)` with **`Δ*(σ) ∝ σ`**. Therefore:

1. recovery is monotone non-decreasing in `Δ`;
2. a collapse exists: recovery → ~0 as `Δ → 0` (credit assignment fails);
3. **the collapse margin scales linearly with noise: `Δ*(2σ0) ≈ 2 · Δ*(σ0)`** (the `(σ/Δ)²`
   signature). `Δ*` is the interpolated `Δ` where recovery crosses 0.5.

## Decision rule (FROZEN)

- **L4C_COLLAPSE_MAPPED** iff, for both noise levels: recovery is monotone in `Δ` (±0.05),
  high at `Δ=0.40` (≥ 0.9) and low at `Δ=0.02` (≤ 0.3) — a genuine collapse — AND the
  σ-scaling holds: `Δ*(2σ0) / Δ*(σ0) ∈ [1.4, 2.8]` (≈ 2, the sqrt-law signature).
- **L4C_NO_COLLAPSE** — no collapse at small `Δ` (recovery stays high): the governor is
  more robust than the sample-complexity law predicts (also an interesting negative).
- **L4C_SCALING_VIOLATED** — a collapse exists but `Δ*` does not scale ~linearly with σ:
  the sample-complexity law does not govern this mechanism.

## Scope / prohibited

Tier `SYNTHETIC-PARAMETRIC`. Characterizes the learned governor's credit-assignment limit
and confirms it is governed by the `(σ/Δ)²` sample-complexity law. Does NOT establish
real-workload behavior, L7, energy/latency, or independent replication. New claim
`CWC-L4c-credit-collapse`; does not change L4/L4a/L4b.
