# A3.1 — Anti-collapse re-run RESULTS (load-balance aux loss)

8 seeds, both stages, lb_coef=0.01 (frozen before run, see
`../../experiments/wp2_mechanism_v2/PREREGISTRATION_A3_1.md`). Controls
unchanged from v2. Data `raw_runs/`, stats `statistics/analysis.json`.

## Verdict
| Stage | A3 verdict | seeds converged | i_norm | route~T | max perm-p |
|---|---|---|---:|---:|---:|
| **A (observable marker)** | **ROUTING_CAUSALITY_SUPPORTED** | **8/8** | 0.999 | 1.000 | 0.001 |
| B (inferred label) | NOT_SUPPORTED | 6/8 | 0.714 | 0.867 | 1.0 |

## Stage A — full claim-tier pass (Act A3)
- learned ce **0.004** = oracle (0.002), acc **1.000**; beats random (2.09),
  frozen (1.98), fixed (2.53) — paired CIs below 0.
- `I_norm(R;T)` = 1.0 on 7/8 seeds, 0.99 on the 8th; permutation `p = 0.001`
  on **all 8**.
- **Interventions (mean, 8 seeds):** force-correct 0.004 (= oracle);
  force-**incorrect** 7.70 → **2078×** worse; module-swap (E_A↔E_B, keep
  routes) 7.70 (predicted catastrophic failure); route-permute 3.72 (destroys
  the advantage). Every causal criterion met.
- The load-balance loss (lb=0.01), fixed on 3 previously-collapsed seeds,
  lifted Stage-A convergence from 5/8 → **8/8** — the collapse was optimization,
  not mechanism, exactly as diagnosed.

## Stage B — inference regime still unreliable
6/8 seeds converge to perfect routing; 2 still collapse. Inferring the required
mechanism from position-1 content (no explicit flag) is harder and lb=0.01 does
not fully break its collapse basin. Below the ≥80% (7/8) bar. This is the named
next gap.

## Bottom line
Routing causality is **SUPPORTED at claim tier in the observable-label regime**
(Stage A): a learned controller allocates the right non-substitutable operator
per input, matches the oracle, and every intervention confirms the causal role
of the route. This is the first fully-supported causal routing result in the
CWC programme. It is NOT yet supported when the mechanism must be inferred
(Stage B, 6/8) — reliability of context inference is the remaining gap before
full A3 and before A4 (RCFR) unblocks.
