# PREREGISTRATION — L4d Higher-Power Scaling Revisit

**Committed before the run.** L4c falsified the `(σ/Δ)²` *noise*-scaling of the governor's
collapse margin (`Δ*` was noise-independent; more noise even helped at `Δ=0.05`). That
anomaly points to an **exploration** effect (reward noise drives softmax churn), not
distinguishability. This revisit (1) raises power and (2) isolates the sample-complexity law
from the noise/exploration confound by scaling the **episode budget** instead of noise.

## Power increase vs L4c

24 controller seeds (was 8); 8-point margin grid `Δ ∈ {0.40, 0.30, 0.20, 0.15, 0.10, 0.07,
0.05, 0.03}` (was 5). Same parametric bandit and REINFORCE governor as L4c.

## Two frozen predictions

**P1 — clean budget-scaling (the isolated sample-complexity law).** At fixed noise
`σ = 0.10`, sweep the episode budget `N ∈ {1500, 3000, 6000, 12000}`. Distinguishing two
arms with margin `Δ` needs `N ∝ (σ/Δ)²`, so the collapse margin scales as
**`Δ*(N) ∝ 1/√N`** — noise is held fixed, so the L4c σ/exploration confound is absent.
Prediction: `Δ*` monotonically DECREASES with `N`, and `Δ*(12000)/Δ*(1500) ≈ 1/√8 = 0.354`.

**P2 — σ-scaling re-test at high power.** At fixed `N = 3000`, `σ ∈ {0.10, 0.20}`, recompute
`Δ*(2σ)/Δ*(σ)` at 24 seeds. Does the L4c noise-independence (`≈0.91`) replicate, or was it a
low-power artifact? Reported, not gated by P1.

`Δ*` = interpolated `Δ` where mean recovery crosses 0.5 (same estimator as L4c).

## Decision rule (FROZEN)

- **L4D_BUDGET_SCALING_CONFIRMED** iff (P1): `Δ*` is monotone non-increasing in `N` AND
  `Δ*(12000)/Δ*(1500) ∈ [0.25, 0.55]` (brackets the `1/√8 = 0.354` law).
- **L4D_BUDGET_SCALING_VIOLATED** — otherwise (the budget sample-complexity law also fails →
  the governor's collapse is not sample-complexity-governed in either axis).
- **P2 reported** as `sigma_scaling_replicates_l4c` (|ratio − 1| ≤ 0.4) vs
  `sigma_scaling_is_samplecomplexity` (ratio ∈ [1.4, 2.8]).

## Scope / prohibited

Tier `SYNTHETIC-PARAMETRIC`. Characterizes the learned-governor mechanism only. New claim
`CWC-L4d-budget-scaling` (SUPPORTED or NOT_SUPPORTED per P1); this run also settles whether
the L4c falsification survives higher power. Does NOT establish real-workload behavior, L7,
energy/latency, or independent replication.
