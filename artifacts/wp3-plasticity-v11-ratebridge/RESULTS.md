# L4i Rate-Function Bridge — RESULTS

**Verdict: `L4I_BRIDGE_CONFIRMED`.** Preregistration:
`experiments/wp3_plasticity_v11_ratebridge/PREREGISTRATION.md`. Reproduce:
`PYTHONPATH=. python -m experiments.wp3_plasticity_v11_ratebridge.src.ratebridge`.

## The learned governor nearly saturates the master rate function `V*(R)`

| flip `p` | `I(C;Z)` bit | `V_gov` (governor) | `V*(I)` (rate function) | saturation `V_gov/V*` | under ceiling |
|---|---|---|---|---|---|
| 0.0 | 1.000 | 0.1909 | 0.1909 | 1.000 | ✓ |
| 0.1 | 0.531 | 0.1499 | 0.1502 | 0.998 | ✓ |
| 0.2 | 0.278 | 0.1090 | 0.1095 | 0.995 | ✓ |
| 0.3 | 0.119 | 0.0680 | 0.0690 | 0.985 | ✓ |
| 0.4 | 0.029 | 0.0270 | 0.0293 | 0.924 | ✓ |
| 0.5 | 0.000 | 0.0000 | 0.0000 | 1.000 | ✓ |

The learned plasticity governor's realised value stays **under** the master value-of-information
rate function `V*(I)` at every information level (the ceiling holds — as data-processing +
`V*`-optimality require), and it **nearly saturates** it: `≥ 92.4%` of the RI optimum everywhere,
`≥ 98%` at high information.

## Why this matters

`V*(R)` (`docs/VALUE_OF_INFORMATION_RATE_FUNCTION.md`) is the sharp maximum value achievable with
`R` nats of information about the context — a converse ceiling the rest of the programme proves.
This experiment shows the ceiling is **not vacuous on a real learned mechanism**: the plasticity
governor comes within ~1.5% of it at high info and ~8% at low info (where committed greedy routing
is slightly less efficient than the rational-inattention soft channel). It is the plasticity analog
of the Act-J pilot's `TRAINED_CONTROLLER_REALISES_V_STAR` — the theory↔learning loop closed on the
plasticity mechanism.

## Consequence for the claim ladder

`CWC-L4i-rate-bridge` is registered **SUPPORTED**: the learned governor realises the master rate
function `V*(R)` (ceiling holds + near-saturation). Ties the L4 sub-line to the information-market
synthesis. Frozen. Does not change L4.

## Scope

Tier `SYNTHETIC`. A theory↔mechanism bridge on the plasticity utility; not a real-workload or L7
result. The `V*` is computed from the synthetic utility, and `V_gov` is the committed greedy
governor (slightly below the RI optimum, hence saturation < 1 at intermediate info).
