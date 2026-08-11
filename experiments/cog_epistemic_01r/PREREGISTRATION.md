# COG-EPISTEMIC-01R — Typed Epistemic Lattice Harness Repair Preregistration

Date frozen: 2026-08-11
Parent: `COG-EPISTEMIC-01` raw non-pass, invalid as complete qualification because F11 had an upstream stochastic precondition failure.
Architecture authority: **NONE**

## Repair question

Does the already-implemented capability-bound epistemic state machine reject every frozen illegal promotion when each attack is constructed so that its own target preconditions are guaranteed by construction rather than by re-running an unrelated stochastic upstream scientific gate?

## What is unchanged

The authority chain, terminal states, evidence classes, transition requirements, PRIMARY metric, cohort size, and all frozen attack semantics F0-F11 are unchanged from `COG-EPISTEMIC-01`.

Primary endpoint remains:

`forbidden_transition_acceptance_rate == 0` in every family in both PRIMARY and REPLICATION.

Secondary legal-chain endpoint remains `1.0`.

No error threshold is weakened.

## Exact repair

Only F10/F11 harness construction changes:

- F10 uses an immutable legacy fixture whose source state is exactly `IDENTIFYING_ASSUMPTION_VIOLATED`.
- F11 uses an immutable legacy fixture whose upstream source state is exactly `CAUSAL_CANDIDATE_UNDER_ASSUMPTIONS` plus a countermodel fixture whose source state is exactly `OBSERVATIONALLY_EQUIVALENT_COUNTERMODEL_SURVIVES`.

These fixtures test the adapter/type transition itself. They do not claim to re-establish or re-test the scientific validity of CSCA-08/COG-COUNTERMODEL-01R, whose frozen artifacts remain separate authority sources.

## Fresh cohorts

- PRIMARY namespace seed: `81001`
- REPLICATION namespace seed: `91001`
- 128 independently bound claim/context cases per family per cohort.

The seeds affect claim ids, evidence hashes, and record/capability digests only; the F10/F11 legacy state fixtures are deterministic by design.

## Failure predicates

FAIL if any forbidden transition succeeds, if any legal chain fails, if any digest invariant fails, if any runtime/harness error occurs, or if the semantic mutation gate fails.

## Non-promotion boundary

A PASS qualifies only a runtime epistemic safety primitive. It does not grant semantic causal truth, real-world identification, replay control, active control, production deployment, large-scale Pareto advantage, or independent external replication.
