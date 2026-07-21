# WP5-AC3 Inferred-Difficulty Boundary — RESULTS

**Verdict: `AC3_BOUNDARY_MAPPED`.** Preregistration:
`experiments/wp5_adaptive_compute/PREREGISTRATION_INFERRED.md`. Reproduce:
`PYTHONPATH=. python -m experiments.wp5_adaptive_compute.src.inferred`.

## The compute-controller's value is bounded by the difficulty information

The controller now sees only a noisy observation `z` of the difficulty (3-symbol symmetric
channel), so it must infer `d` and the compute decision has a real cost. Held-out recovery vs the
mutual information `I(C;Z)`:

| flip `p` | `I(C;Z)` bit | recovery (mean, 8 inits) | worst |
|---|---|---|---|
| 0.000 | 1.585 | **+1.000** | +1.000 |
| 0.100 | 1.016 | +0.795 | +0.795 |
| 0.200 | 0.663 | +0.591 | +0.591 |
| 0.350 | 0.301 | +0.284 | +0.284 |
| 0.500 | 0.085 | +0.049 | +0.049 |
| 0.667 | 0.000 | **+0.000** | +0.000 |

Recovery falls **monotonically** as the difficulty becomes harder to infer, reproduces the
given-difficulty AC2 result at full information (`1.000`), and vanishes at zero information
(`0.000`) — with the controller **abstaining** (never routing itself below the best fixed compute).
The value-of-information boundary — the master inequality `V_realized ≤ oracle_gap − c_route` made
quantitative — holds on the **compute** mechanism exactly as it did on plasticity (L4b).

## Consequence

The compute axis now mirrors the plasticity arc through three rungs: **AC1** (identifiable) →
**AC2** (learned controller recovers it) → **AC3** (its value is information-bounded). The
information-market theory governs a *second* real mechanism, not just plasticity.

`CWC-AC3-inferred-difficulty` is registered **SUPPORTED**. It does not establish real-workload
routing or L7.

## Scope

Tier `SYNTHETIC`. Route-decision-cost / value-of-information boundary on the compute mechanism.
