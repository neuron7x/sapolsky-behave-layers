# 10 — Integration decisions — ACT-R&D-01 first pass

Date: 2026-08-10

## Governing rule
No external mechanism is integrated into CWC runtime from semantic similarity alone. This pass creates research candidates only. Reproduction, null attack and OOD replication remain mandatory before architecture promotion.

## S01 — Counterfactual Shapley Credit Assignment
Decision: **RESEARCH_CANDIDATE / P0 REPRODUCTION**.

Why: the formal object is directly relevant to deferred causal credit and explicitly separates skill from luck using trajectory-specific counterfactuals. It is stronger than the current heuristic debt score as a credit *definition*, but requires an SCM/counterfactual simulator and a baseline policy. CWC will not replace `resolution_aware_debt()` until a matched-budget reproduction demonstrates better cause ranking and false-credit control after estimator cost.

## S02 — Abstraction / brain alignment
Decision: **RESEARCH_CANDIDATE / REPRESENTATION TEST ONLY**.

Why: the paper supports a relationship between representational abstraction, intrinsic dimension and brain encoding, plus a model-weight intervention during brain tuning. It does not establish that brain and model share a mechanism. CWC transfer is therefore restricted to the testable proposition that semantic-state representations should survive paraphrase and context shifts better than lexical identities for downstream causal effects.

## S03 — NeuroWorld
Decision: **RESEARCH_CANDIDATE / LEAKAGE-CONTROLLED LATENT DYNAMICS**.

Why: past-only stimulus access and next-latent rollout are strong engineering constraints for a world-state model. However, `causal` here primarily means temporally admissible conditioning, not identified interventional stimulus causality. CWC may test transition sufficiency and rollout stability, but must not inherit a biological or causal-effect claim.

## S04 — Dynamic predicate invention
Decision: **RESEARCH_CANDIDATE / ARCHIVE ABSTRACTION ONLY**.

Why: Predict-Verify-Refine and reusable predicates fit the failure-memory philosophy, but evidence is from deterministic fully observable gridworlds with user-selected metarules/types. Predicate invention is only admissible if it improves OOD prediction/transfer after a description-complexity penalty and beats a no-invention flat-symbolic baseline.

## Promotion state
All four sources stop at `CLAIM_EXTRACTED`. None is `REPRODUCED`, `NULL_ATTACKED`, `OOD_REPLICATED`, `MECHANISM_SUPPORTED`, or `ARCHITECTURE_CANDIDATE` in this pass.

## Pass-1 execution update

S01 has now passed two *narrow synthetic* qualifiers (Skill/Luck conceptual separation and exact OOD cause ranking), but remains below `REPRODUCED` for the imported mechanism because the paper's efficient estimator/training/PTR stack and a matched-budget comparison with existing CWC replay policies have not been reproduced.

S03's first independently implemented controlled transfer test is retained as a negative result: despite large mean short/mid-horizon gains, the preregistered h=8 OOD robustness predicate failed at 54/64 seeds versus the frozen 56/64 requirement. This result does not falsify NeuroWorld; it kills only the specific CWC controlled-transfer hypothesis/configuration tested here.

## ACT-R&D-02 / CSCA-01 — 2026-08-10

**Decision:** `NO_ARCHITECTURE_INTEGRATION / CONTROLLED_MECHANISM_RETAINED`.

The exact counterfactual-credit kernel passed the frozen controlled SCM, OOD seed replication,
and zero-cause nulls. A 64-permutation independent Monte-Carlo approximation also passed the
preregistered rank qualifier. This does **not** authorize integration because the local source
record is snapshot-only (`QUARANTINED`), the exact kernel uses oracle structural counterfactuals,
real-model utility is untested, and H5 remains human-gated.

Weakest causal link after this result: **counterfactual-model adequacy**. The next admissible attack
must quantify how simulator/model misspecification converts into false causal credit before any
real-model replay integration.
