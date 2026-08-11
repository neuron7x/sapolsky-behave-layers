# COG-MEMORY-01 — Execution Report

**Date:** 2026-08-11  
**Preregistration commit:** `6746ab022fa8cda066ebfe66bcca4634d6881973`  
**Verdict:** `ASSUMPTION_AWARE_MEMORY_CONSOLIDATION_QUALIFIED_SYNTHETIC_NARROWED`  
**Authority:** `EPISTEMIC_MEMORY_PRIMITIVE_ONLY`

## Objective

Test whether an immutable assumption-aware memory ledger can preserve the authority
of typed COG-EPISTEMIC-01R records, block false causal consolidation, preserve
countermodel debt, and propagate evidence invalidation through dependent memories.

## Frozen adversarial families

- `M0`: OBSERVED factual storage.
- `M1`: PREDICTIVE storage.
- `M2`: ASSUMPTION_CONDITIONAL without a listed finite countermodel.
- `M3`: ASSUMPTION_CONDITIONAL with surviving countermodels.
- `M4`: INTERVENTION_SUPPORTED with empty countermodel set.
- `M5`: INTERVENTION_SUPPORTED with a surviving countermodel.
- `M6`: terminal states (`UNIDENTIFIED/FALSIFIED/OOD/ABSTAIN`).
- `M7`: three-level dependency chain followed by parent retraction.
- `M8`: assumption invalidation with dependent fan-out.
- `M9`: tampered epistemic binding / direct-construction attack.
- `M10`: legacy string authority injection.
- `M11`: stronger later epistemic record must not mutate an older memory in place.

Each family used 128 cases in PRIMARY (`seed_base=82001`) and 128 fresh cases in
REPLICATION (`seed_base=92001`).

## Confirmatory result

Every family passed `128/128` in both cohorts. Across both cohorts:

- false causal consolidations: `0`;
- invariant failures: `0`;
- event-chain failures: `0`;
- M7 transitive parent-retraction rate: `1.0`;
- M8 assumption-invalidation transitive retraction rate: `1.0`;
- M9 tampered-binding acceptance rate: `0.0`;
- M10 legacy-string injection acceptance rate: `0.0`;
- M11 in-place authority upgrade: rejected in every case.

The semantic gate self-test killed `6/6` frozen mutations.

## What qualified

The supported runtime memory API now preserves the typed epistemic boundary during
consolidation and retraction. In particular, assumption-conditional memories remain
quarantined, surviving countermodels veto active causal consolidation, and parent or
assumption invalidation propagates transitively.

## What did not qualify

No claim is made for semantic causal truth, planning value, replay control, active
control, autonomous self-modification, large-scale architecture promotion, malicious
host unforgeability, or external independent replication.
