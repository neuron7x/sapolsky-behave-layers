# L4k Falsification Boundary — RESULTS

**Verdict: `L4K_LINE_SURVIVES`** (after a disclosed fix to a mis-specified null — the harness
caught a design error, see below). Preregistration:
`experiments/wp3_plasticity_v13_killtest/PREREGISTRATION.md`. Reproduce:
`PYTHONPATH=. python -m experiments.wp3_plasticity_v13_killtest.src.killtest`.

## The line's foundation survives its most decisive kill-conditions

| condition | interaction | `G_lo` (δ=0.05) | governor recovery | behaves? |
|---|---|---|---|---|
| **real** (control) | present | **+0.111** | 1.000 | ✓ gap present |
| **additive null** | removed (ANOVA) | −0.053 | 0.000 | ✓ vanishes |
| **collapsed null** | removed (same row) | −0.080 | 0.000 | ✓ vanishes |
| **aligned-best null** | removed (best arms coincide) | −0.080 | 0.000 | ✓ vanishes |

The cost-budget gap appears **only** when a genuine context×arm interaction is present, and
**vanishes** (`G_lo ≤ 0`, governor recovery 0) under every interaction-destroying null. The whole
L4 line's foundation — that the gap is a real interaction, not a structural artifact — is not
falsified by its most decisive kill-conditions.

## The harness caught my own error (why this is credible)

The first run flagged `L4K_LINE_FALSIFIED`. The cause was **not** a real falsification — it was a
**broken null**: the original `arm_shuffle` derangement `[1,0,2,3]` merely relabeled context 1's
arms, moving its best arm to a *different but still distinct* index, so the interaction was
preserved and the gap correctly persisted. That is not a valid null. The two canonical nulls
(additive, collapsed) had already vanished. The mis-specified null was replaced (disclosed
amendment) with `aligned_best`, which moves context 1's argmax onto context 0's argmax index so a
single fixed arm is optimal for both — genuinely destroying context-conditioning. It vanishes. The
false alarm was a design bug in the test, transparently corrected.

## Consequence for the claim ladder

`CWC-L4k-falsification-boundary` is registered **SUPPORTED**: the L4 line survives its decisive
foundation nulls. Necessary, not sufficient, for external validity (still synthetic, no L7).
Frozen.

## Scope

Tier `SYNTHETIC`. A falsification-boundary / foundation check; surviving synthetic nulls does not
establish real-workload validity or L7.
