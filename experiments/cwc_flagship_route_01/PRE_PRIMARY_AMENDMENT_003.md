# CWC-FLAGSHIP-ROUTE-01 — PRE-PRIMARY AMENDMENT 003

Status: FROZEN BEFORE ANY PRIMARY OR REPLICATION MODEL EXECUTION.

## Trigger

The first CALIBRATION serialization exposed an operational hermeticity defect: checkpoint metadata stored the host-absolute `/mnt/data/...` path. The checkpoint bytes, SHA-256, calibration rows, ridge coefficients, frontier slopes, seeds, data hashes, routing rule, endpoints, and all scientific thresholds were otherwise already determined.

## Frozen repair

Checkpoint metadata MUST store repository-relative POSIX paths rooted at the repository (for example `artifacts/cwc-flagship-route-01/checkpoints/seed74101.pt`). Existing calibration checkpoint metadata may be normalized in-place only if its checkpoint SHA-256 revalidates before rewriting metadata. The model checkpoint bytes MUST NOT be regenerated or modified by this repair.

This amendment changes serialization/provenance portability only. It MUST NOT change model weights, calibration observations, fitted coefficients, frontier slopes, continuation rule, comparator definitions, compute accounting, PRIMARY seeds, REPLICATION seeds, or promotion criteria.
