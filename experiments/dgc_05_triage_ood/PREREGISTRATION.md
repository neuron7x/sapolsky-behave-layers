# DGC-05 — Software-Triage OOD / Combinatorial Generalization

Date frozen: 2026-08-22
Status: PRE-EXECUTION / NO DGC-05 OUTPUT OBSERVED
Parent evidence: DGC-04 `SOFTWARE_TRIAGE_SUPPORTED_NARROW`.

## Question

Does the DGC terminal-decision rule generalize to **fault combinations not present in DGC-04**, and does governance fail closed when a changed domain has no registered diagnostic authority?

## Frozen known fault universe

Known fatal domains: `A,H,C,S,I`, with the same actual validators and mutation mechanisms as DGC-04.

DGC-04 observed task IDs are excluded from the generalization cohort. DGC-05 known-combination cohort is every non-empty subset of `{A,H,C,S,I}` not already present in DGC-04. This yields 21 unseen combinations.

For each known task, changed domains equal the injected fault domains. Policies retain the frozen diagnostic order `A,H,C,S,I`.

## Unknown-domain OOD cases

Three additional cases are frozen:

- `U`;
- `A+U`;
- `I+U`.

`U` is a changed repository domain with no registered validator. The autonomous governance action MUST be `RELEASE_ABSTAIN` before any `RELEASE_PASS` authority is possible. Unknown-domain cases are not counted as release PASS/DENY classification tasks; they test fail-closed scope authority.

## Policies on known combinations

- B0 FULL: all five diagnostics;
- B1 PATH ROUTER: all changed known-domain diagnostics;
- B2 DGC: same admissible diagnostics but stop at first fatal detection.

## Gates

`TRIAGE_COMBINATORIAL_OOD_SUPPORTED` requires on all 21 unseen known combinations:

1. DGC release-decision accuracy = 1.0;
2. false-pass count = 0;
3. full task coverage;
4. DGC validator-call count < path-router validator-call count < full validator-call count.

`UNKNOWN_DOMAIN_FAIL_CLOSED` requires all three unknown-domain cases to return `RELEASE_ABSTAIN` and never `RELEASE_PASS`.

No change to DGC-04 result is permitted. DGC-05 is a separate generalization claim limited to this fault family and repository validator topology.
