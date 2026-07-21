# PREREGISTRATION — L4i Rate-Function Bridge (governor ↔ V*(R))

**Committed before the run.** L4b showed the plasticity governor's realised value tracks
`I(C;Z)` linearly. This connects the mechanism to the master **value-of-information rate
function** `V*(R)` (`docs/VALUE_OF_INFORMATION_RATE_FUNCTION.md`,
`experiments/common/value_of_information_rate.py`): does the learned governor's realised value
stay **under** `V*(I)` (theory holds as ceiling) and how close does it come?

## Design (frozen)

- Utility `U` = aggregate `U_λ=1[t,a]` over the held-out confirmatory seeds (13–20), contexts
  {lexical, relational}, uniform prior. `gap = oracle_gap_value(U)`.
- For the L4b noisy-context channel (flip probability `p`), mutual information
  `I(C;Z) = 1 − H₂(p)` bits (`= R` nats after ln2 scaling).
- **Governor realised value** (above best-fixed): the committed-routing value
  `V_gov(p) = max(0, (1 − 2.146·p)) · gap` (exact for the greedy governor; abstention floors it
  at 0), evaluated at `p ∈ {0, 0.1, 0.2, 0.3, 0.4, 0.5}`.
- **Rate-function optimum**: `V*(I) = optimal_value_at_rate_ri(U, R=I·ln2, prior)`.

## Predictions (frozen)

1. **Ceiling holds:** `V_gov(I) ≤ V*(I) + 1e-6` at every `p` (data-processing: the governor uses
   at most `I(C;Z)` bits, and `V*` is the max value at that budget).
2. **Near-saturation:** the governor is close to the RI optimum — `V_gov(I) / V*(I) ≥ 0.90` at
   every `p` with `V*(I) > 0`.

## Decision rule (FROZEN)

- **L4I_BRIDGE_CONFIRMED** iff both predictions hold (ceiling + near-saturation ≥ 0.90).
- **L4I_CEILING_ONLY** — the ceiling holds but saturation `< 0.90` at some `p` (governor bounded
  but not near-optimal).
- **L4I_CEILING_VIOLATED** — `V_gov > V*(I)` at some `p` (theory or info-accounting is wrong —
  a red flag).

## Scope / prohibited

Tier `SYNTHETIC`. A theory↔mechanism bridge: the learned plasticity governor realises the master
rate function. New claim `CWC-L4i-rate-bridge`. Does not establish real-workload behavior, L7,
energy/latency, or independent replication.
