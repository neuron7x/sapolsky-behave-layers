# L4h Context-Scaling Generalization — RESULTS

**Verdict: `L4H_GENERALIZES`.** Preregistration:
`experiments/wp3_plasticity_v10_contexts/PREREGISTRATION.md`. Reproduce:
`PYTHONPATH=. python -m experiments.wp3_plasticity_v10_contexts.src.contexts`.

## Identifiability and governor recovery hold as contexts scale

| contexts \|C\| | `G_lo` (δ=0.05) | identifiable | worst governor recovery |
|---|---|---|---|
| 2 | +0.084 | ✓ | 1.000 |
| 3 | +0.385 | ✓ | 1.000 |
| 4 | +0.535 | ✓ | 1.000 |
| 6 | +0.685 | ✓ | 0.952 |

At **constant per-context budget** (so `|C|` is the only variable), identifiability strengthens
and governor recovery stays `≥ 0.95` across `|C| = 2..6`. Contexts do **not** interfere — the
2-context result generalizes.

## Honest reading

- `G_lo` **grows** with `|C|`: more specialized contexts make context-conditioning more valuable
  (the oracle beats any single fixed arm by more), and the certificate's `√|C|` deviation term
  tightens — so identifiability gets *easier* with more contexts, not harder.
- Governor recovery dips slightly at `|C|=6` (`0.952`), the first sign that a single shared
  softmax over many context-arm pairs is marginally harder to train — but it stays well above the
  0.8 bar at matched per-context budget. The earlier collapse studies (L4c–L4f) show where this
  eventually breaks (thin margins / budget dilution), not here.

## Consequence for the claim ladder

`CWC-L4h-context-scaling` is registered **SUPPORTED**: the identifiability + governor result
generalizes to more contexts at constant per-context budget. Frozen. Does not change L4.

## Scope

Tier `SYNTHETIC-PARAMETRIC`. A generalization check to more contexts (the real benchmark has 2
tasks); not a real-workload or L7 result.
