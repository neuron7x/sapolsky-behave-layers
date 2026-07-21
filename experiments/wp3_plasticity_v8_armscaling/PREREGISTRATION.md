# PREREGISTRATION — L4f Arm-Count Scaling of the Collapse Exponent

**Committed before the run.** L4e found the collapse-margin budget exponent depends on arm
count: 2 arms → `−1.12` (drift-limited), 4 arms → `−0.65` (mixed). It attributed the shift to
"dead-arm suppression injects diffusion." This tests that as a **monotone law**: sweep the
number of arms and predict the exponent shallows toward the diffusion limit as arms are added.

## The predicted law

With `K` arms (2 real: best `b`, runner-up `r`; `K−2` dead arms paying 0), the softmax dilutes
the `b`-vs-`r` probability mass (early `π_b ≈ 1/K`) and the resolving drift
`dg/dt ∝ Δ·π_b·π_r` is suppressed, while the dead arms' decaying mass adds an effective
diffusion transient. So the collapse exponent should **shallow monotonically toward `−0.5`
(pure diffusion) as `K` grows**, starting from the 2-arm drift limit `≈ −1`.

## Design (frozen)

- Same REINFORCE governor and budget/Δ sweeps as L4e (24 controller seeds, extended Δ grid to
  0.001, budgets `N ∈ {1500,3000,6000,12000}`, `σ=0.10`).
- **Arm sweep** `K ∈ {2, 3, 4, 6, 8}` (means: arm 0 best for context 0, arm 1 best for context
  1, both runner-up `1−Δ`, arms `2..K−1` dead at 0). For each `K`, fit the budget exponent =
  log-log slope of `Δ*` vs `N`.

## Decision rule (FROZEN)

- **L4F_ARM_SCALING_MAPPED** iff:
  (1) the exponent is **monotone non-decreasing** in `K` (shallower with more arms;
      `exp(K_{i+1}) ≥ exp(K_i) − 0.10` tolerance);
  (2) it clearly shallows: `exp(8) − exp(2) ≥ 0.25`;
  (3) `exp(2) ≤ −0.9` (reproduces the 2-arm drift limit).
- **L4F_NO_ARM_DEPENDENCE** — the exponent is flat in `K` (range `< 0.15`): the L4e "dead arms
  add diffusion" account is falsified.
- **L4F_NON_MONOTONE** — the exponent varies with `K` but not monotonically.
- **L4F_INSTRUMENT_LIMITED** — residual off-grid `NaN` (extend grid).

## Scope / prohibited

Tier `SYNTHETIC-PARAMETRIC`. Characterizes the governor-collapse mechanism's arm-count
dependence. New claim `CWC-L4f-arm-scaling`. Does not establish real-workload behavior, L7,
energy/latency, or independent replication.
