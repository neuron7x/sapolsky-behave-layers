# WP5-AC4 Compute Rate-Function Bridge — RESULTS

**Verdict: `AC4_RATE_BRIDGE_CONFIRMED`.** Preregistration:
`experiments/wp5_adaptive_compute/PREREGISTRATION_RATEBRIDGE.md`. Reproduce:
`PYTHONPATH=. python -m experiments.wp5_adaptive_compute.src.ratebridge`.

## The compute-controller's value stays under V*(R), tight at high information

| flip `p` | `I(C;Z)` bit | `V_gov` | `V*(I)` | saturation | under ceiling |
|---|---|---|---|---|---|
| 0.000 | 1.585 | 0.4582 | 0.4582 | 1.000 | ✓ |
| 0.100 | 1.016 | 0.3644 | 0.3753 | **0.971** | ✓ |
| 0.200 | 0.663 | 0.2707 | 0.2917 | 0.928 | ✓ |
| 0.350 | 0.301 | 0.1301 | 0.1718 | 0.757 | ✓ |
| 0.500 | 0.085 | 0.0226 | 0.0692 | 0.326 | ✓ |
| 0.667 | 0.000 | 0.0000 | 0.0000 | 1.000 | ✓ |

The master rate function `V*(I)` is a **valid ceiling** on the learned compute-controller at every
information level, and it is **tight at high information** (saturation `≥ 0.971` for `I ≥ 1` bit).
The theory→learning loop is closed on the compute mechanism too.

## Honest cross-mechanism finding (documented, not gated)

Saturation **falls at low information** (`0.326` at `I=0.085` bit), unlike the 2-context plasticity
bridge (L4i, `≥0.924` everywhere). The reason is real and disclosed a priori: the committed greedy
controller is **not** the rational-inattention soft-routing optimum at sub-bit information, and that
gap **widens with the number of contexts** (3 here vs 2 in plasticity). So the rate function bounds
both mechanisms, but the committed controller saturates it near-fully only when information is
plentiful or contexts are few. A future RI-trained compute-controller would close the low-info gap.

## Consequence — the compute arc is a structural twin of plasticity

`AC1` (identifiable) → `AC2` (learned controller recovers) → `AC3` (value info-bounded) → `AC4`
(realises `V*(R)`) mirrors `L4 → L4a → L4b → L4i`. The value-of-information theory governs **two
independent real mechanisms** — parameter-plasticity and adaptive-compute — not one.

`CWC-AC4-rate-bridge` is registered **SUPPORTED**. No real-workload, no L7.

## Scope

Tier `SYNTHETIC`. Committed-greedy controller (documented sub-RI at low info).
