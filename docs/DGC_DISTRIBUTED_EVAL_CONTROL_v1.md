# DGC Distributed Evaluation Control Plane v1

Status: `ENGINEERING_CONTROL_PRIMITIVE / NOT SCALE EVIDENCE`

## Purpose

Deterministic, fail-closed coordination for distributed confirmatory evaluation without weakening evidence integrity.

## Hard invariants

1. Work population is frozen as `task × policy × replicate`.
2. Claim order is deterministic for identical state.
3. Leases have bounded TTL and retry count.
4. Worst-case per-unit cost is reserved before dispatch.
5. Structurally underbudgeted experiments are rejected before execution.
6. Stale/forged/expired leases cannot commit.
7. Identical duplicate commits are idempotent.
8. Conflicting duplicate results quarantine the unit.
9. Completion requires all preregistered units; cherry-picking cannot mint a certificate.
10. Every state transition is hash-chained for audit.

## Claim boundary

This closes an engineering control-plane gap. It does **not** prove frontier-scale operation. Actual multi-node throughput, queueing, accelerator utilization, network partition recovery, cloud reliability, load/soak and cost evidence remain external obligations.

## 2026 context

Adaptive inference is now explicitly treated as constrained compute allocation and production scheduling. DGC therefore needs evidence-preserving distributed execution, not merely throughput. This coordinator is the authority layer around future frozen SWE-bench / Terminal-Bench confirmatory runs.
