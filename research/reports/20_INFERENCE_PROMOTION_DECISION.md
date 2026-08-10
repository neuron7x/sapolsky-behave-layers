# ACT-R&D-03 — Inference Promotion Decision

**Decision:** `NO_PROMOTION`  
**Current authority:** `RESEARCH_ONLY`  
**Target `SHADOW_INFERENCE_QUALIFIED`: NOT REACHED**

## Binding reasons

1. Frozen PRIMARY held-out coverage was `43/224 = 0.1919642857`, below the preregistered `>=0.20` requirement. The independent replication cohort reached `45/224 = 0.2008928571`; replication success cannot overwrite the primary failure.
2. Both cohorts had zero accepted false causal authority under the preregistered aggregate candidate-set metric, while the no-abstention comparator had `96/224 = 0.4285714286` false authority in each cohort. This is informative safety evidence but does not satisfy the conjunction gate.
3. The mandatory post-confirmatory context attack found 12 accepted `M10_CONTEXT_DEPENDENT_CAUSALITY` cases with `context_stability=0.5`. The current policy therefore can issue one global candidate while the preferred candidate changes across contexts. This exposes a missing conditional-authority primitive.
4. `M11_SHARED_MODEL_CLASS_MISSPECIFICATION`, zero-cause, latent-confounder-shift and insufficient-support attacks abstained/rejected as intended. Those successes do not rescue the failed context/coverage gates.

## Consequence

`Shapley / counterfactual credit remains OFFLINE_RESEARCH_ONLY.`

No real-model shadow pilot, replay control, physical compute qualification, direct logit control, weight update or architecture promotion is authorized by ACT-R&D-03.

## Next admissible mechanism

A successor experiment must represent **context-conditional causal authority** rather than a single global candidate. It must be newly preregistered and use fresh calibration/confirmatory seeds. The existing 20% coverage threshold may not be weakened post hoc.
