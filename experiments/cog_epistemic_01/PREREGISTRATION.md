# COG-EPISTEMIC-01 — Typed Epistemic Lattice Preregistration

Date frozen: 2026-08-11
Mode: confirmatory software/epistemic safety gate
Parent: `COG-COUNTERMODEL-01R`
Architecture authority: **NONE**

## Question

Can CWC replace ad-hoc string authority states at the live cognitive boundary with an immutable, capability-gated epistemic state machine such that stronger causal authority cannot be constructed without the exact evidence class required by the transition?

## P0 formal object

The admitted positive authority chain is:

`OBSERVED < PREDICTIVE < ASSUMPTION_CONDITIONAL < INTERVENTION_SUPPORTED`.

The absorbing fail-closed states are:

`UNIDENTIFIED`, `FALSIFIED`, `OOD`, `ABSTAIN`.

These absorbing states are deliberately not interpreted as lower positive evidence tiers. They are terminal dispositions. A new evidence channel requires a new record lineage; it may not silently resurrect a terminal record.

## Capability rule

Every strengthening transition must consume a capability token cryptographically bound to:

- the exact claim id;
- the exact parent-record digest;
- the exact context scope;
- one or more SHA-256-addressed evidence references;
- the evidence class required by the transition.

Required capabilities:

- `OBSERVED -> PREDICTIVE`: predictive-validation evidence;
- `PREDICTIVE -> ASSUMPTION_CONDITIONAL`: explicit identifying-assumption capability with non-empty assumption ids;
- `ASSUMPTION_CONDITIONAL -> INTERVENTION_SUPPORTED`: direct-intervention capability. Surrogate/replay/counterfactual-model evidence is not admissible as direct-intervention evidence.

Terminal transitions may only reduce authority.

## Primary endpoint

`forbidden_transition_acceptance_rate == 0` over the frozen adversarial transition matrix in both PRIMARY and REPLICATION.

## Secondary endpoints

1. `legal_transition_acceptance_rate == 1`.
2. `cross_claim_capability_reuse_acceptance_rate == 0`.
3. `stale_parent_capability_reuse_acceptance_rate == 0`.
4. `scope_escalation_acceptance_rate == 0`.
5. `surrogate_as_direct_intervention_acceptance_rate == 0`.
6. `terminal_resurrection_acceptance_rate == 0`.
7. canonical record digest is deterministic and changes whenever authority-bearing payload changes.
8. legacy CSCA-08 and COG-COUNTERMODEL-01R decisions are mapped fail-closed without modifying their frozen result artifacts.

## Frozen adversarial families

F0 — direct construction bypass.
F1 — wrong capability class on each positive transition.
F2 — `UNIDENTIFIED -> INTERVENTION_SUPPORTED` resurrection attempt.
F3 — `FALSIFIED -> positive` resurrection attempt.
F4 — assumption-conditional promotion with no direct intervention evidence.
F5 — surrogate/replay trace mislabeled as direct intervention.
F6 — token replay against a different claim.
F7 — token replay against a stale/different parent digest.
F8 — context/scope escalation.
F9 — evidence hash or evidence-class mutation.
F10 — legacy `IDENTIFYING_ASSUMPTION_VIOLATED` incorrectly promoted to causal support.
F11 — legacy surviving countermodel incorrectly collapsed to positive causal authority.

## Confirmatory cohorts

The experiment is deterministic over a fixed adversarial case generator but will use independent UUID namespace seeds for PRIMARY and REPLICATION to ensure token ids/digests differ while transition semantics remain identical.

- PRIMARY seed namespace: `COG-EPISTEMIC-01:PRIMARY:61001`
- REPLICATION seed namespace: `COG-EPISTEMIC-01:REPLICATION:71001`
- 128 cases per family per cohort where randomization is meaningful; deterministic API-construction attacks are repeated with 128 independently bound claims/scopes.

No threshold may be tuned after PRIMARY.

## Failure predicates

Scientific/software qualification FAILS if any of the following occurs in either cohort:

- any forbidden transition succeeds;
- any legal chain step fails;
- terminal state can be promoted in-place;
- surrogate evidence can mint direct-intervention authority;
- capability can be replayed across claim, parent digest, or wider scope;
- a legacy assumption violation or surviving observational countermodel maps to `INTERVENTION_SUPPORTED`;
- record or capability digest is non-deterministic for identical canonical content;
- gate self-test fails to kill every frozen authority mutation.

## Non-promotion boundary

A PASS qualifies only the **epistemic runtime safety primitive**. It does not establish semantic causality, real-world causal identification, useful replay, active control, large-model transfer, Pareto advantage, or independent external replication.

`INTERVENTION_SUPPORTED` itself is operator/context scoped. It is not equivalent to `TRUE_CAUSAL_MODEL` or semantic truth.
