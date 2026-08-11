# COG-EPISTEMIC-01R — Preregistration

Status: FROZEN BEFORE R1 EXECUTION.

Parent negative: `COG-EPISTEMIC-01` is immutable and remains failed.

## Single repair

F11 previously conditioned the downstream countermodel-collapse test on a stochastic upstream regime-IV decision being positive on every seed. That is not the property under test and creates a false harness failure whenever the upstream evaluator correctly abstains/rejects.

R1 changes only F11 composition: construct a typed `ASSUMPTION_CONDITIONAL` upstream record through the legal lattice path, run the actual set-valued countermodel search on the frozen synthetic family, and require a surviving observationally-equivalent countermodel to force `UNIDENTIFIED`. It does not use a stochastic upstream causal-candidate gate.

All other illegal-transition families and thresholds are unchanged.

## Fresh cohort namespaces

PRIMARY_R1: 81001 namespace base.
REPLICATION_R1: 91001 namespace base.
128 cases/family/cohort.

## Primary endpoint

- legal positive chain acceptance = 1.0 in each cohort;
- forbidden transition acceptance = exactly 0 in every family and cohort;
- unexpected/harness error count = 0;
- deterministic digest invariants pass;
- unconditional causal truth remains unavailable.

Any failure => `TYPED_EPISTEMIC_LATTICE_R1_NOT_QUALIFIED`.
