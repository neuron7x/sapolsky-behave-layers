# COG-COUNTERMODEL-01R — Agent Handoff

## Current boundary

Parent `COG-COUNTERMODEL-01` is a frozen design-negative. Do not rewrite it.

R1 verdict: `SET_VALUED_COUNTERMODEL_GUARD_QUALIFIED_SYNTHETIC_NARROWED`.

Qualified primitive:

`surviving factual-law equivalence set -> block causal consolidation`

`explicit structural bound -> narrow set conditionally, never upgrade bound to truth`

`invalid upstream epistemic state -> countermodel search cannot promote it`

## Next P0

Implement `COG-EPISTEMIC-01` as a typed runtime lattice, not status strings. Minimum states:

`OBSERVED`, `PREDICTIVE`, `ASSUMPTION_CONDITIONAL`, `INTERVENTION_SUPPORTED`, `UNIDENTIFIED`, `FALSIFIED`, `OOD`, `ABSTAIN`.

Required invariant: no code path may construct a stronger authority state unless it presents the exact evidence/assumption capability token required by that transition. Mutation tests must attack every forbidden transition, especially `UNIDENTIFIED -> INTERVENTION_SUPPORTED`, `ASSUMPTION_CONDITIONAL -> INTERVENTION_SUPPORTED` without intervention evidence, and any route from `FALSIFIED` to a positive authority state.

Do not begin assumption-aware memory consolidation until this lattice passes.
