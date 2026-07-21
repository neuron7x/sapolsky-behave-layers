# L4g Cost-Model Robustness — RESULTS

**Verdict: `L4G_ROBUST`.** Preregistration:
`experiments/wp3_plasticity_v9_costrobust/PREREGISTRATION.md`. Reproduce:
`PYTHONPATH=. python -m experiments.wp3_plasticity_v9_costrobust.src.costrobust`.

## The L4 gap survives every cost shape

| cost transform | head penalty | `G_lo` (δ=0.05) | identifiable | governor recovery |
|---|---|---|---|---|
| linear `x` | 0.062 | **+0.111** | ✓ | 1.000 |
| sqrt `√x` | 0.250 | **+0.101** | ✓ | 1.000 |
| log `log(1+x)` | 0.693 | **+0.035** | ✓ | 1.000 |
| square `x²` | 0.004 | **+0.043** | ✓ | 1.000 |

Under all four monotone cost normalizations — spanning sub-linear (`log` even makes the cheap
`head` group *expensive*, penalty 0.69) to super-linear (`square`) — the oracle gap stays
identifiable (`G_lo > 0`) and the reward-only governor recovers it fully on held-out seeds. The
L4 result is **not** an artifact of the linear cost model.

## Honest reading

The gap **magnitude** does depend on the cost shape: `log` compresses it to `G_lo=0.035`
(because it flattens the head-vs-attn cost ratio), vs `0.111` linear. But it never crosses zero,
and the governor still finds the context-conditioned allocation, because the cost *ordering*
(head < attn < mlp) is preserved by any monotone transform — and it is the ordering, not the
curvature, that makes the cost-budget interaction real.

## Consequence for the claim ladder

`CWC-L4g-cost-robust` is registered **SUPPORTED**: L4 identifiability is robust to the cost
model (validity check passed). Strengthens L4. Frozen. Does not change L4's status.

## Scope

Tier `SYNTHETIC`. Robustness of the L4 identifiability claim to the cost normalization only.
