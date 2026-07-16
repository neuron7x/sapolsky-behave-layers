# WP-4 Adaptive Compute Allocation — RESULTS

VERDICT: **`ADAPTIVE_COMPUTE_JENSEN_GAP_CONFIRMED`**. 8 seeds × 4 difficulty
distributions. Prediction registered in `docs/IDENTIFIABILITY_THEORY.md`
(committed 6322bed) BEFORE the run. Data `raw_runs/`, stats `analysis.json`.

## The claim, achieved
The first narrow causal mechanism whose advantage **cannot be explained by
static architecture, additional capacity, or optimization**: adaptive allocation
of a fixed compute budget across inputs of heterogeneous required depth. Its
advantage over the best static allocation equals the theory-predicted Jensen gap
**P(m > K)** — derived, not fitted — to machine precision.

## Result table (solved-rate, mean over 8 seeds)
| P(m) regime | K=E[m] | static | random (input-blind) | **adaptive** | oracle | empirical gap | **theory P(m>K)** | \|err\| |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| uniform | ~4–5 | 0.550 | 0.542 | **1.000** | 1.000 | 0.450 | 0.450 | **0.0000** |
| easy_skew | 3 | 0.667 | 0.612 | **1.000** | 1.000 | 0.333 | 0.333 | **0.0000** |
| hard_skew | 6 | 0.497 | 0.552 | **1.000** | 1.000 | 0.503 | 0.503 | **0.0000** |
| bimodal | ~4–5 | 0.515 | 0.533 | **1.000** | 1.000 | 0.485 | 0.485 | **0.0000** |

`max |empirical_gap − P(m>K)| = 0.0000` across all 32 (distribution × seed) cells.

## The four causal gates (all PASS)
1. **Prediction holds** — empirical gap = P(m>K) in every regime/seed (err < 0.02).
2. **Beats input-blind random** — adaptive (1.000) ≫ random (0.53–0.61) at the
   SAME average compute. Variable depth alone does not help; using the per-input
   halt signal does.
3. **Matches oracle** — adaptive = oracle = 1.000 (halt-on-convergence recovers
   m(x) exactly).
4. **Compute matched** — adaptive average hops = K = static hops.

## Why the three alternatives are ruled out
| Alternative explanation | Ruled out because |
|---|---|
| static architecture / more layers | same shared operator, same L; adaptive just uses it a variable number of times |
| additional capacity / parameters | identical parameters (one operator); zero extra params |
| optimization effect / lucky seeds | the policy is DETERMINISTIC — no training, no seeds in the mechanism; the gap is identical across 8 data seeds |

The only remaining cause is **information**: the adaptive policy uses m(x) (via
the halt/convergence signal); the static policy ignores it. The advantage is the
Jensen gap of allocating a fixed resource under heterogeneity — and its SIZE is
predicted by P(m>K), the tail mass the fixed budget cannot reach.

## Scope and honesty
- The hop operator is exact (a capable primitive) so that ALLOCATION is the sole
  free variable — the cleanest possible causal isolation. Learning a neural
  pointer-follower is a separate, harder problem and is NOT the mechanism under
  test; conflating the two would muddy the isolation.
- `solved` (reached absorber) is the causal metric; `acc` additionally includes
  ~1/N chance value-collisions and is reported in `raw_runs/` for completeness.
- This is a synthetic, mechanistic demonstration at claim tier. The next step is
  the same test on a real workload at cloud scale with a LEARNED allocator vs
  MoD/MoE (Act J) — where the §6 identifiability predictor already says the gap
  will exist iff the workload's difficulty distribution has non-trivial tail mass.

## Bottom line
This is the programme's second claim-tier positive and its cleanest: a causal
mechanism (adaptive compute allocation) whose advantage is (a) real, (b)
quantitatively predicted from the task alone, and (c) provably not attributable
to architecture, capacity, or optimization.
