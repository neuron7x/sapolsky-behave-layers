# COG-MEMORY-01 — Assumption-Aware Epistemic Memory Consolidation Preregistration

Date frozen: 2026-08-11
Parents: `COG-COUNTERMODEL-01R`, `COG-EPISTEMIC-01R`
Architecture authority: **NONE**

## Question

Can CWC consolidate memory without converting unresolved assumptions, surviving countermodels, terminal epistemic states, or stale evidence into stronger causal authority, while propagating later invalidation transitively through dependent memories?

## Required memory object

Every memory record must bind:

- exact `EpistemicRecord.record_digest`;
- exact epistemic state;
- claim id and context scope;
- assumption ids;
- evidence SHA-256 values;
- surviving countermodel ids;
- dependency memory ids;
- immutable event-chain provenance.

The memory layer may not infer authority from legacy status strings.

## Consolidation policy

- `OBSERVED`: may be stored as active factual memory; `causal_consolidated=false`.
- `PREDICTIVE`: may be stored as active predictive memory; `causal_consolidated=false`.
- `ASSUMPTION_CONDITIONAL`: must remain `QUARANTINED`; it is never causal-consolidated, even when no finite countermodel was found.
- `INTERVENTION_SUPPORTED`: may be active causal memory only when no surviving countermodel id is attached; operator/context scope remains binding.
- `UNIDENTIFIED`, `FALSIFIED`, `OOD`, `ABSTAIN`: cannot create active causal memory.
- any active memory whose required assumption is invalidated must be retracted/quarantined according to the frozen rule and every dependent memory must be transitively retracted.
- a stronger later epistemic record never mutates an older memory in place; it requires a new memory record/version.

## Primary endpoints

In both PRIMARY and REPLICATION:

1. `false_causal_consolidation_rate == 0` across all unsafe families.
2. `required_transitive_retraction_rate == 1.0`.
3. `legal_noncausal_storage_rate == 1.0` for OBSERVED/PREDICTIVE.
4. `legal_intervention_scoped_causal_storage_rate == 1.0` only when the countermodel set is empty.
5. `legacy_string_injection_acceptance_rate == 0`.
6. `tampered_memory_binding_acceptance_rate == 0`.

## Frozen adversarial families

M0 OBSERVED factual storage.
M1 PREDICTIVE storage.
M2 ASSUMPTION_CONDITIONAL with no listed finite countermodel.
M3 ASSUMPTION_CONDITIONAL with surviving countermodels.
M4 INTERVENTION_SUPPORTED with empty countermodel set.
M5 INTERVENTION_SUPPORTED with surviving countermodel.
M6 terminal epistemic states.
M7 explicit parent retraction over a three-level dependency chain.
M8 identifying-assumption invalidation over a dependency fan-out.
M9 tampered record/evidence binding.
M10 legacy string/status injection.
M11 stronger later epistemic record cannot mutate the older memory in place.

## Cohorts

- PRIMARY namespace seed: `82001`
- REPLICATION namespace seed: `92001`
- 128 independently bound cases per family per cohort.

## Failure predicates

FAIL if any unsafe family becomes causal-consolidated, if any mandatory dependent survives a parent/assumption retraction, if factual/predictive legal storage fails, if clean operator-scoped intervention memory cannot consolidate, if a legacy string is accepted, if a tampered binding verifies, if the event hash chain breaks, or if the semantic mutation gate fails.

## Non-promotion boundary

A PASS qualifies only the memory consolidation/retraction primitive. It does not establish semantic causality, long-horizon planning value, replay benefit, active control, autonomous self-modification, large-model transfer, deployment safety, or external replication.
