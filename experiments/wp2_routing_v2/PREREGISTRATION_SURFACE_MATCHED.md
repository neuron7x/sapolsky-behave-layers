# Retrospective protocol — surface-matched end-to-end routing (Routing v3)

> Historical-status correction (2026-07-19): protocol, implementation and
> results first entered Git in the same commit; this is not independently
> timestamped preregistration evidence.

The protocol addresses the surface caveat left open by
`runner_r3c_reinforce` (which ran on a benchmark with length/histogram leakage).

## Question
`runner_r3c_reinforce` showed a REINFORCE controller routes near-perfectly on the
S-R-O benchmark — but that benchmark has surface cues (leakage_probe AUROC=1.0), so
the controller may route on surface, not structure. Here EASY/HARD (NEAR/FAR) are
**surface-matched by construction** (identical length, first token, token multiset;
leakage_probe ~0.5). Difficulty is a purely STRUCTURAL property: the distance
between the two occurrences of the one duplicated value.

Two hypotheses:
- **H_cheap-route:** the structural route signal is cheaply computable; a controller
  much cheaper than the global mechanism still routes FAR→global under a budget.
- **H_route-is-compute:** predicting the route requires ~the same computation as the
  expensive mechanism; a cheap controller routes at chance, so routing saves nothing.

## Design
Mechanisms are EXACT operators (no module learning): `local_logits(w)` solves NEAR
only; `global_logits` always solves. Controller trained end-to-end by REINFORCE
with per-use cost (L=L_task+λ·C_use), NO label/target/label-derived-capacity. Eval
routes top-K at fixed label-free budget 0.5. **Four arms:**
1. cheap controller (mean-pool MLP), REINFORCE;
2. attn controller (self-attention, O(L²)), REINFORCE — pre-empts "controller too weak";
3. cheap controller, **supervised probe** on the far label — representational ceiling;
4. attn controller, supervised probe — representational ceiling.

Arms 3–4 disambiguate "structure inaccessible to this controller" (probe AUROC≈0.5)
from "RL credit-assignment failed" (probe AUROC high, RL low).

## Preregistered decision rule (≥8 seeds)
- **H_route-is-compute SUPPORTED** iff BOTH REINFORCE arms give eval AUROC 95%
  interval overlapping 0.5 (no routing better than chance) AND BOTH supervised
  probes give AUROC 95% interval overlapping 0.5 (structure not cheaply learnable).
- **H_cheap-route SUPPORTED** iff any arm gives eval AUROC lower bound > 0.5 AND
  learned_loss < random_loss with the paired 95% upper bound < 0.

Sanity anchors (must hold or the benchmark is mis-built): `all_global_loss ≈ 0`,
`all_local_loss` large (local fails on the FAR half).

## Meaning if H_route-is-compute
This BOUNDS the routing claim generally: adaptive routing has cheap value only when
the "which mechanism is needed" signal is cheaply computable from the input (e.g.
surface cues). When difficulty is a deep structural property, the routing decision
IS the computation and routing saves nothing. This extends the identifiability
theorem with a **route-decision-cost** term the original omitted.
