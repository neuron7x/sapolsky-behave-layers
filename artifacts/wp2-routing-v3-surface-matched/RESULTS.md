# Surface-matched end-to-end routing — route-decision-cost boundary

**Verdict:** `ROUTE_DECISION_IS_THE_COMPUTATION` (resolves **H_route-is-compute**)

## Arms (≥8 seeds each)
| arm | metric | value | 95% CI |
|---|---|---|---|
| cheap REINFORCE | eval AUROC | 0.5081 | [0.5013, 0.5152] |
| attn REINFORCE | eval AUROC | 0.5137 | [0.5052, 0.5215] |
| cheap supervised probe | AUROC | 0.4897 | [0.4796, 0.5003] |
| attn supervised probe | AUROC | 0.498 | [0.4897, 0.5056] |

Benchmark sanity: all-global loss 0.0018 ≈ 0, all-local loss 1.8597 (local fails on FAR). ✓

## Meaning
On a surface-matched benchmark (leakage_probe ~0.5), NEITHER a cheap mean-pool controller NOR a self-attention controller can route FAR->global above chance under REINFORCE, AND neither can even LEARN the NEAR/FAR property under DIRECT supervision. The failure is therefore not RL credit-assignment and not controller weakness: the structural difficulty signal is not cheaply computable. Predicting the route costs ~the same as running the expensive mechanism, so routing saves nothing. This BOUNDS the routing claim: adaptive routing has cheap value ONLY when the 'which mechanism is needed' signal is cheaply computable from the input (e.g. surface cues, as in the leaky S-R-O benchmark where the same REINFORCE controller reached AUROC 1.0). It extends the identifiability theorem with a route-decision-cost term the original omitted.

## Companion
artifacts/wp2-routing-v3-r3c-reinforce/ (AUROC 1.0 WITH surface cues) — the contrast that localizes the value to cheap route-signal computability.
