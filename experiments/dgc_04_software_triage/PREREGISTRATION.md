# DGC-04 — Real Software-Engineering Release-Triage Pilot

Date frozen: 2026-08-22
Status: PRE-EXECUTION / NO DGC-04 WORKLOAD RESULTS OBSERVED

## Question

Can DGC reduce **actual verification work** on repository fault-injection tasks without changing the externally relevant release decision?

The decision is binary: `RELEASE_PASS` or `RELEASE_DENY`. Diagnostic completeness is secondary; once a fatal invariant is detected, additional diagnostics have zero value for this release decision and DGC must stop.

## Real execution substrate

Each task is a disposable copy of real repository files. Diagnostics call the existing executable validators:

1. `architecture_gate.validate`;
2. `hermeticity_gate.validate`;
3. `complexity_gate.validate`;
4. `build_sbom.validate`;
5. `inference_integrity_gate.validate`.

Fault mutations are the same classes already used by `scripts/assurance_attack.py`:

- A: forbidden cross-boundary import;
- H: network dependency in the hermetic reproduction path;
- C: complexity-budget regression;
- S: SBOM tamper;
- I: inference-validation bypass.

## Frozen workload

Eleven equal-weight tasks:

`CLEAN, A, H, C, S, I, A+H, C+S, H+I, A+C+S, A+H+C+S+I`.

`CLEAN` marks all five diagnostic domains as changed but injects no fault, so a safe policy cannot infer PASS without executing the relevant diagnostics.

## Policies

- `B0_FULL`: execute all five diagnostics for every task.
- `B1_PATH_ROUTER`: execute every diagnostic whose declared path-domain intersects the task's changed paths.
- `B2_DGC`: same admissible path-domain set as B1, fixed diagnostic order `A,H,C,S,I`, but stop immediately after the first fatal detection because the release action is already invariant (`RELEASE_DENY`).

No result-dependent reordering or path-rule changes are allowed.

## Primary endpoints

For every policy:

- release-decision accuracy against injected ground truth;
- false-pass count (catastrophic); 
- validator-call count;
- wall-clock validator time (secondary, environment-specific).

## Success gate

`SOFTWARE_TRIAGE_SUPPORTED_NARROW` iff:

1. B2 DGC release-decision accuracy = 1.0;
2. B2 false-pass count = 0;
3. B2 validator-call count < B1 validator-call count < B0 validator-call count;
4. no task is dropped;
5. every injected mutation is detected by at least one executed validator before a deny decision.

The pilot does not establish model/API token savings. It tests the core DGC invariant on a real engineering decision: once the admissible action cannot change, additional cognition/verification is not purchased.
