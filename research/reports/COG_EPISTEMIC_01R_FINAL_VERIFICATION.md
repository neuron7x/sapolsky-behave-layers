# COG-EPISTEMIC-01R — Final Verification

Verdict: `TYPED_EPISTEMIC_LATTICE_R1_QUALIFIED_SYNTHETIC_NARROWED`.

## What changed

CWC now has a capability-bound typed epistemic runtime. Positive authority is represented only by the chain:

`OBSERVED -> PREDICTIVE -> ASSUMPTION_CONDITIONAL -> INTERVENTION_SUPPORTED`.

Fail-closed dispositions are `UNIDENTIFIED`, `FALSIFIED`, `OOD`, and `ABSTAIN`; they are absorbing within a record lineage. `TRUE_CAUSAL_MODEL` is intentionally not a state.

Promotion tokens are bound to claim id, parent-record digest, evidence class, evidence SHA-256, and exact context scope. Surrogate/replay evidence cannot mint direct-intervention authority. Historical string-state outputs are adapted without rewriting frozen artifacts.

## Parent negative

The first `COG-EPISTEMIC-01` confirmatory execution is preserved as failed. Its F11 composition family incorrectly required a stochastic upstream CSCA-08 evaluator to produce a positive candidate on every seed; one replication seed legitimately returned `IDENTIFYING_ASSUMPTION_VIOLATED`, which the harness itself treated as an error. R1 prospectively isolated the downstream property and used fresh cohort namespaces.

## R1 confirmatory results

- PRIMARY_R1: 128 legal chains accepted; all 12 forbidden-transition families 0/128 accepted.
- REPLICATION_R1: 128 legal chains accepted; all 12 forbidden-transition families 0/128 accepted.
- No unexpected/harness errors.
- Digest determinism and payload-sensitivity checks passed in both cohorts.
- Semantic gate self-test killed 6/6 authority/type mutations.
- Focused typed-epistemic tests: 16 passed.
- Repository test collection: 482 tests, zero collection errors.
- `py_compile` and `git diff --check` passed.

## Authority boundary

Qualified only as an epistemic runtime safety primitive. It does not establish semantic causality, real-trace identification, replay control, active control, or architecture promotion. `INTERVENTION_SUPPORTED` means evidence exists for the explicitly named operator and scope; it does not mean the latent world model is universally true.

## Next gate

`COG-WORLDS-02`: generalize countermodel generation from the current linear/regime family to nonlinear temporal SCMs, hidden-confounder alternatives, representation-equivalent models, and mechanism shifts. The output must remain set-valued: surviving causally distinct worlds block consolidation.
