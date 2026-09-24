# DGC Continuous Assurance v1

Status: `CONTROL_LOGIC_IMPLEMENTED / PRODUCTION_EVIDENCE_ABSENT`

## Purpose

Translate post-deployment evidence into a fail-closed control decision for shadow, canary and later production stages.

The categories follow the six monitoring families identified by NIST AI 800-4 (2026):

1. Functionality
2. Operational
3. Human Factors
4. Security
5. Compliance
6. Large-Scale Impacts

## Machine semantics

A frozen `MonitoringSpec` binds monitoring to one deployment digest and defines:

- required categories;
- per-category freshness cadence;
- categories requiring human validation;
- maximum aggregate WARN risk before HOLD.

Observations bind category, metric, tick, status, risk, deployment digest, evidence digest and source identity.

Decision hierarchy:

- any required category missing/stale -> `HOLD`;
- missing required human validation -> `HOLD`;
- WARN risk above frozen threshold -> `HOLD`;
- any current FAIL -> `ROLLBACK`;
- only complete, fresh, validated evidence with no failed gate -> `CONTINUE`.

Cross-deployment evidence and conflicting duplicate observations are rejected.

## Claim boundary

This is control-plane implementation, not evidence that DGC has been safely deployed. No current production monitoring population exists. `PRODUCTION_CONTROL_AUTHORIZED=false` remains unchanged.

## Current targeted authority

Local targeted tests: `7/7 PASS`.

Adversarial monitoring gate: `4/4 attacks killed`, covering missing telemetry, stale telemetry, security failure and cross-deployment evidence injection.

## Remaining obligations

Real shadow/canary monitoring must still demonstrate actual instrumentation coverage, distributed log integrity, incident response, human review capacity, monitoring overhead and sustained operation under real workload drift.
