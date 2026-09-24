# DGC-04 Pre-Execution Amendment 001 — Detection Semantics

Date: 2026-08-22
Status: PRE-EXECUTION; no DGC-04 workload outputs observed.

The preregistration success-gate item 5 says “every injected mutation is detected by at least one executed validator before a deny decision.” That wording conflicts with the explicitly preregistered DGC terminal rule: once the first fatal mutation is detected, `RELEASE_DENY` is invariant and remaining diagnostics must not run.

The intended and decision-consistent requirement is frozen as:

> For every failing **task**, at least one injected fatal mutation must be detected by an executed validator before `RELEASE_DENY`; no task may be falsely passed. Complete enumeration of all simultaneous faults is not a primary endpoint because it cannot change the release decision.

No workload, fault composition, diagnostic order, policy, metric, or threshold changes. This amendment only resolves the internal contradiction before implementation/execution.
