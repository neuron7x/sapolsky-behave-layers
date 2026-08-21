# DGC Claim Boundary

**Programme:** Decision-Gradient Computing (DGC)  
**Status:** `RESEARCH_HYPOTHESIS / ENGINEERING_CANDIDATE`  
**Claim authority:** this file constrains language only; empirical authority remains `claim_registry.json`.

## Allowed initial claim

> DGC is an experimental compute-governance mechanism that admits additional inference resources according to estimated decision-relevant value of computation rather than uncertainty alone.

## Formal object

The project name "Decision Gradient" does **not** imply that the current estimator is a differential gradient. Until a perturbation geometry and derivative normalization are defined and validated, the executable object is a **weighted counterfactual decision-regret sensitivity estimator**:

\[
R_i = U(w'_i,a_i^*) - U(w'_i,a_0) \ge 0,
\qquad
\widehat G_D = \frac{\sum_i q_iR_i}{\sum_i q_i}.
\]

`q_i` are declared non-negative scenario/plausibility weights. They MUST NOT be described as posterior probabilities unless a calibrated probabilistic semantics is separately established.

## Hypothesis DGC-H1

At matched total inference budget, DGC improves preregistered `NetDecisionValue` over the best preregistered baseline on the frozen synthetic oracle workload, or achieves non-inferior decision quality at lower total compute cost.

## Prohibited claims before confirmatory evidence

- AGI architecture;
- human-like cognition;
- globally optimal metareasoning;
- universal compute-efficiency superiority;
- safety guarantee;
- novel mathematical theory;
- universal superiority over routing, early exit, test-time scaling, MoE, active learning, Bayesian experimental design, or sequential testing;
- production readiness;
- causal interpretation of text-only countermodels without a structural causal model or equivalent intervention semantics.

## Promotion ladder

`RESEARCH_ONLY -> EXPERIMENTALLY_SUPPORTED -> SUPPORTED_GENERALIZING`

Promotion requires the preregistered primary endpoint, untouched held-out seeds/workloads, and the exact negative-result rules in `docs/DGC_INTEGRATION_AND_VERIFICATION_PROTOCOL.md`.
