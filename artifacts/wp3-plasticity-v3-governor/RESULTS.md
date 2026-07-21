# L4a Learned-Governor — RESULTS

**Verdict: `L4A_SUPPORTED`.** Preregistration:
`experiments/wp3_plasticity_v3_governor/PREREGISTRATION.md` (committed before the run).
Reproduce: `PYTHONPATH=. python -m experiments.wp3_plasticity_v3_governor.src.governor`.

## Result — a reward-only governor recovers the full gap out-of-sample

A per-context softmax policy trained by REINFORCE (moving-average baseline), learning
from the reward of the sampled arm ONLY (never the oracle label), trained on seeds 5–12
and evaluated on held-out seeds 13–20:

| Policy (held-out realised `U_λ=1`) | Value |
|---|---|
| random arm | 0.2568 |
| best fixed arm (`head`, chosen on train) | 0.5278 |
| **learned governor (worst of 8 controller seeds)** | **0.7187** |
| oracle (ceiling) | 0.7187 |
| **recovery** `(learned−fixed)/(oracle−fixed)`, worst seed | **1.000** |

The learned governor recovers **100%** of the L4 oracle gap on held-out seeds, in **every
one of 8 independent controller initializations** — it discovers the oracle allocation
(cheap `head` → lexical, expensive `attn` → relational) from reward alone and generalizes
out of sample. `random < best_fixed` confirms the baselines are ordered correctly.

## NULL falsifier — the instrument can report "no gap"

Re-running the identical pipeline on a **collapsed** benchmark (both contexts given the
same reward row, so no context-conditioning can help) yields **`null_recovery = 0.000`**
(≤ 0.10). The governor does not manufacture a gap where none exists — the positive result
is not an artifact of a permissive metric.

## Honest reading

The benchmark margins are **wide** (lexical: head 0.938 vs next 0.68; relational: attn
0.500 vs next 0.12) and reward noise is small, so a competent governor is *expected* to
succeed — this was stated in the preregistration. The informative content is therefore
not difficulty but: (1) **reward-only credit assignment works** here (contrast the routing
R3-C straight-through *collapse*), (2) it **generalizes** to held-out seeds, and (3) the
**NULL falsifier** makes the claim refutable.

## Consequence for the claim ladder

L4's standing limitation "no learned governor (exact oracle only)" is **discharged in this
regime**: a learned, reward-only governor achieves the confirmed gap out of sample.
`CWC-L4-plasticity` stays `SUPPORTED_NARROWED` (its narrowing is now *given-context,
wide-margin, synthetic* — not *oracle-only*).

## Scope (tier `SYNTHETIC`, given-context)

Does NOT establish: inferred-context or surface-independent routing (context is given
here, `c_route=0`), compute-equivalent Pareto (L7), energy/latency advantage,
real-workload generalization, or independent replication.
