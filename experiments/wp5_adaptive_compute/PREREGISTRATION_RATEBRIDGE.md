# PREREGISTRATION — WP5-AC4 Compute Rate-Function Bridge

**Committed before the run.** Closes the compute arc as the twin of the plasticity L4i bridge:
does the learned compute-controller's realised value stay under the master rate function `V*(R)`,
and how close does it come? Note in advance (from the AC3 committed-routing recovery, which is
already committed evidence): the compute mechanism has 3 contexts and the committed controller
abstains at low info, so — unlike the 2-context plasticity case — saturation is expected to be
high near full information and to fall at low information (committed greedy ≠ rational-inattention
soft-routing). The preregistration is scoped accordingly.

## Design (frozen)

- Utility `U` = aggregate `U_λ=0.5[d][K]` over held-out seeds 4–7. `gap = oracle_gap_value(U)`.
- Controller realised value at each noise `p` (from the committed AC3 sweep):
  `V_gov(p) = max(0, recovery_mean(p)) · gap`.
- Rate-function optimum: `V*(I) = optimal_value_at_rate_ri(U, I·ln2, prior)` at
  `I = I(C;Z)(p)` from AC3.

## Predictions (frozen)

1. **Ceiling holds (the theory claim):** `V_gov(I) ≤ V*(I) + 1e-6` at **every** info level.
2. **High-info near-saturation:** `V_gov/V* ≥ 0.90` for every `I ≥ 1.0` bit.
3. **Documented (not gated):** low-info saturation falls (committed greedy vs RI soft-routing),
   reported explicitly — the committed controller is not RI-optimal at sub-bit information, and the
   gap widens with the number of contexts.

## Decision rule (FROZEN)

- **AC4_RATE_BRIDGE_CONFIRMED** iff predictions 1 AND 2 hold. The master rate function is a valid,
  high-info-tight ceiling on the learned compute-controller.
- **AC4_CEILING_ONLY** — ceiling holds but high-info saturation `< 0.90` (bounded but not tight).
- **AC4_CEILING_VIOLATED** — `V_gov > V*(I)` somewhere (theory/info-accounting wrong).

## Scope / prohibited

Tier `SYNTHETIC`. Theory↔mechanism bridge on the compute mechanism; committed-greedy controller
(a documented gap to the RI optimum at low info). New claim `CWC-AC4-rate-bridge`. No real-workload,
no L7.
