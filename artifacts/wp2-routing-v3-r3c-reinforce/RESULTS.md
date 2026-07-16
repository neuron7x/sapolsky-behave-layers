# R3-C REINFORCE — end-to-end routing credit-assignment falsification

**Verdict:** `ROUTING_END_TO_END_SUPPORTED_UNDER_BINDING_BUDGET` (resolves **H_opt**)

## Preregistered decision (PREREGISTRATION_R3C_REINFORCE.md)
- mean learned_loss 0.0089 < mean random_loss 0.4802 ✓
- paired (learned−random) 95% upper bound -0.465 < 0 ✓
- worst-seed AUROC 1.0 > 0.5 ✓
- balanced acc 0.9942, symmetric NMI 0.954, induced route fraction 0.5057 (budget 0.5)

## What changed vs the straight-through R3-C
Only the controller's credit-assignment: straight-through top-K → REINFORCE with a mean-reward advantage baseline and an explicit per-use FLOP cost. Same task, same frozen modules, same label-free fixed budget, same metrics.

## Honest boundary
This runs on task_semantic_route, where leakage_probe reported length/histogram AUROC=1.0. The controller may route on surface cues; structure-vs-surface is NOT yet separated. The fully-clean test needs the surface-matched benchmark with mechanism-appropriate modules.

## Meaning
The earlier end-to-end COLLAPSE was an artifact of the straight-through top-K estimator, not an absence of signal. A REINFORCE controller with the honest L=L_task+lambda*C_use objective recovers oracle-level routing, but ONLY under a binding budget (lambda>=1); at lambda<=0.5 it collapses to semantic-everywhere and the route inverts. This confirms the identifiability theorem's central claim: adaptive routing is identifiable ONLY as a constrained (budgeted) property.
