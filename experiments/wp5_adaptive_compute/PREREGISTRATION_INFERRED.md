# PREREGISTRATION — WP5-AC3 Inferred-Difficulty Boundary

**Committed before the run.** AC2 gave the controller the true difficulty for free. This makes
difficulty **inferred** from a noisy observation `z`, so the compute decision has a real cost and
can fail; its realisable value should be bounded by the information `I(C;Z)`. The compute-axis
analog of the L4b plasticity boundary.

## Design (frozen)

- Reward `U_λ=0.5[d][K]` from the committed AC1 raw runs (8 seeds), difficulties `d ∈ {1,2,3}`,
  compute `K ∈ {1,2,3}`. Train seeds `{0,1,2,3}`, eval held-out `{4,5,6,7}`.
- **Noisy observation:** each episode draws true `d` uniform and `z = d` with prob `1−p`, else one
  of the other two difficulties uniformly. 3-symbol symmetric channel; mutual information
  `I(C;Z) = log₂3 + (1−p)log₂(1−p) + p·log₂(p/2)`.
- **Noise sweep** `p ∈ {0.0, 0.1, 0.2, 0.35, 0.5, 0.667}` ⇒ `I(C;Z) ≈ {1.585, 1.016, 0.663, 0.301,
  0.085, 0.000}` bits.
- **Controller:** softmax `π(K|z)` on the OBSERVATION only, REINFORCE from the true-difficulty
  reward, 8 inits; held-out greedy recovery `= (realised − best_fixed)/(oracle − best_fixed)`.

## Predictions (frozen)

1. `recovery(p=0) ≥ 0.9` (reproduces the given-difficulty AC2 result).
2. recovery is **monotone non-increasing** in `p` (increasing in `I(C;Z)`).
3. a boundary exists: `recovery(p=0.667) ≤ 0.15` (zero information ⇒ no realisable gap).
4. the controller **does not route itself below fixed** at high noise (worst recovery `≥ −0.05` at
   every `p` — it abstains rather than mis-routing).

## Decision rule (FROZEN)

- **AC3_BOUNDARY_MAPPED** iff predictions 1–4 all hold.
- **AC3_NOT_MAPPED** — monotonicity fails, or `recovery(I≈0) > 0.15` (a manufactured gap with no
  information ⇒ broken), or `recovery(0) < 0.9`.

## Scope / prohibited

Tier `SYNTHETIC`. Route-decision-cost / value-of-information boundary on the compute mechanism. New
claim `CWC-AC3-inferred-difficulty`. Does not establish real-workload, L7, or independent replication.
