# Act-J Identifiability Pilot — RESULTS

**Verdict: `PILOT_GO_L4_CONFIRMATORY`.** Preregistration:
`experiments/act_j_pilot_decision/PREREGISTRATION.md` (committed before this run).
Reproduce: `PYTHONPATH=. .venv/bin/python experiments/act_j_pilot_decision/src/runner.py`.

## Decision

| Quantity | Value |
|---|---|
| Primary candidate | cost-budget plasticity, `λ = 1.0` (real `wp3-plasticity-v1`, 5 seeds) |
| `Ĝ` (plug-in oracle gap) | **0.1906** |
| `G_lo` (debiased, δ_eff, one-sided) | **0.0808** |
| `δ` / `δ_eff` (Bonferroni over `Λ={0,.5,1,2}`) | 0.05 / **0.0125** |
| `|C|`, `|A|` | 2, 4 |
| max per-cell `se` (= σ/√5) | 0.0280 |
| `c_route` (given-task regime) | 0.0 |
| **route-cost headroom** (max `c_route` the GO survives) | **0.0808** |
| Decision rule | GO iff `G_lo(λ=1; δ_eff) > c_route` |

`G_lo = 0.0808 > c_route = 0` ⇒ **GO**. The certificate subtracts the max-operator
optimism and the sampling + selection deviation from `Ĝ = 0.1906` and the remaining
lower bound is still strictly positive: the plasticity cost-budget mechanism is
**identifiable at 1−δ_eff confidence**.

## Controls (the pilot can fail — and two arms correctly do)

| Control | Purpose | `Ĝ` | `G_lo` | identifiable? | expected |
|---|---|---|---|---|---|
| NEG_A weak-interaction (`λ=0`) | quality/retention has no dominant interaction | ~0 | ≤ 0 | **False** ✓ | not id. |
| NEG_B quality-dominance (routing `[[1,1],[.004,1]]`) | unconstrained plug-in gap = 0 | 0 | ≤ 0 | **False** ✓ | not id. |
| POS specialization (`[[1,0],[0,1]]`) | genuinely identifiable at the same noise | 0.5 | > 0 | **True** ✓ | id. |
| certificate self-falsification | calibrated FPR ≤ δ, naive rule fails | — | — | `all_ok=True` ✓ | valid |

Both negatives are refused and the positive is green-lit **at the primary pilot's own
noise level** — so the GO is not an artifact of a permissive instrument.

## What this GO means — and does not

- **Means:** spend the next *confirmatory* increment on a cost-aware plasticity run
  (freeze `λ` before execution, cost-aware oracle objective, fresh held-out split) —
  the identifiability signal survives honest debiasing, so the L4 run is not doomed.
- **Does NOT mean:** L7 compute-equivalent Pareto, a learned allocator, energy/latency
  advantage, or real-workload generalization. No trained checkpoint exists locally;
  no LM pilot was run. This is **offline identifiability**, tier
  `SYNTHETIC_ADJACENT / OFFLINE`.
- **Fragility to record:** the headroom is thin (0.0808). The GO holds only while the
  route decision is near-free — true in the given-task regime (task identity observed),
  but a deployment that must *detect* the task boundary could consume the headroom. The
  confirmatory run must charge `c_route` explicitly.

## λ sweep (transparency)

`G_lo` is reported at every grid point with the same `δ_eff`; `λ=1` is the frozen
operating point. See `verdict.json → lambda_sweep`.
