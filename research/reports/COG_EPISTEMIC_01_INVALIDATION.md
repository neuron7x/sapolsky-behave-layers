# COG-EPISTEMIC-01 — Confirmatory Run Invalidation Record

Date: 2026-08-11
Raw verdict: `TYPED_EPISTEMIC_LATTICE_NOT_QUALIFIED`
Status: **INVALID AS A COMPLETE QUALIFICATION TEST — HARNESS PRECONDITION DEFECT**

The raw PRIMARY/REPLICATION run is preserved verbatim under:

- `research/results/COG-EPISTEMIC-01/verdict.json`
- `artifacts/cog-epistemic-01/transition_matrix.csv`
- `artifacts/cog-epistemic-01/SHA256SUMS`

## What happened

All legal chains passed (`128/128` in both cohorts) and every forbidden transition family except one had `0/128` acceptance in both cohorts.

The sole recorded failure was:

`REPLICATION / F11_LEGACY_COUNTERMODEL_COLLAPSE / case 42`

The row did **not** contain a successful illegal epistemic transition. Its harness detail was:

`HARNESS_STATE_ERROR: IDENTIFYING_ASSUMPTION_VIOLATED`.

F11 was intended to test only this typed mapping:

`legacy ASSUMPTION_CONDITIONAL candidate + surviving factual-law countermodel -> UNIDENTIFIED`.

Instead, the confirmatory harness regenerated a stochastic CSCA-08 upstream IV experiment and assumed that every nominally valid synthetic draw would enter `CAUSAL_CANDIDATE_UNDER_ASSUMPTIONS`. At one replication seed the upstream multiplicity-controlled diagnostic rejected the identifying assumption, so the target F11 adapter transition was never exercised.

## Why the run cannot simply be rescued

The frozen primary endpoint required every F11 replication case to exercise the declared forbidden-promotion target. Reclassifying or dropping the failed seed after observing it would be post-hoc cohort editing. Therefore the original run remains non-passing and is not used as positive evidence.

## Repair principle

A fresh experiment id `COG-EPISTEMIC-01R` must isolate the runtime type-safety question from stochastic upstream scientific qualification. F10/F11 will use immutable legacy-decision fixtures that encode the exact historical API states being mapped; the new test will not rerun the IV science merely to construct a state-machine precondition.

Fresh claim/digest namespaces and a new preregistration are mandatory. No thresholds from the failed run may be weakened.
