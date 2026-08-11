# COG-EPISTEMIC-01R — Agent Handoff

## Qualified primitive

`evidence -> typed state -> capability-bound legal transition -> immutable lineage`

R1 verdict: `TYPED_EPISTEMIC_LATTICE_QUALIFIED_SYNTHETIC_NARROWED`.

The parent `COG-EPISTEMIC-01` raw non-pass is frozen and must remain preserved.

## Hard runtime invariants

- no `UNKNOWN/UNIDENTIFIED -> CAUSAL` shortcut exists;
- terminal states are absorbing within a record lineage;
- assumption evidence cannot substitute for direct intervention evidence;
- replay/surrogate model output cannot mint direct-intervention authority;
- tokens are bound to exact claim, parent digest, and context scope;
- `INTERVENTION_SUPPORTED` is operator/context scoped and never means true causal model.

## Next P0

`COG-MEMORY-01 — Assumption-Aware Consolidation`.

Memory must store the typed epistemic record itself (or its digest plus bound evidence), surviving countermodel ids, assumption ids, context scope, and dependency edges. Consolidation may occur only when policy admits the record state. A later terminal downgrade/retraction must invalidate dependent memories transitively. No memory layer may reconstruct authority from legacy strings.
