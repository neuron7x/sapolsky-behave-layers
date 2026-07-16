# CWC Verification and Validation Plan

## Verification (code ⟷ spec)
Confirms: spec compliance, schema compliance, determinism, budget invariants,
serialization, checkpoint/resume, numerical reference, error handling, release
integrity. Executed by `make -f Makefile.cwc verify` (ruff, mypy --strict, unit +
property + mutation + determinism + experiment tests) and the doc-status gate
(`scripts/doc_status_gate.py`).

## Validation (experiment ⟷ scientific construct)
Confirms: construct validity, benchmark identifiability, oracle necessity, causal
dependence, control adequacy, generalization scope, statistical support, absence of
forbidden leakage, and claim⟷evidence agreement. Executed per experiment via its
preregistration + `verdict.json` + the analyzers, and recorded in `VALIDATION_RECORD.md`.

## Traceability
`REQUIREMENTS_TRACEABILITY_MATRIX.csv` links requirement → implementation → test →
experiment → artifact → claim. A claim with an unclosed critical requirement is not
allowed.

## Acceptance
critical requirements without tests = 0; critical scientific requirements without
validation = 0; claims without traceability = 0; stale records = 0.
