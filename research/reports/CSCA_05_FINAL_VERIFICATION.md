# CSCA-05 — Final Verification Record

Date: 2026-08-10

## Scientific boundary

Authoritative verdict: `DIRECT_INTERVENTION_SHADOW_RUNTIME_QUALIFIED_NARROWED`.
The qualified object is the explicitly bounded direct-intervention shadow measurement
path on the small nanochat runtime. Broad learned-model shadow inference, replay
control, GPU/production-compute qualification, semantic causality, and active causal
control remain unauthorized.

## Post-execution integrity defects found and repaired

1. `scripts/csca05_gate.py` initially reconstructed the trace-manifest hash in
   lexicographic filename order (`CODE` before `PROSE`) although the authoritative
   runner sealed `PROSE[0..31]` then `CODE[0..31]`. Every individual trace hash was
   already correct. The gate was repaired to reconstruct the original generation
   order; no result artifact or scientific threshold changed.
2. `H4-CSCA-05.json` had been frozen before execution using an ad-hoc field layout
   rather than the canonical `HumanDecision` schema. A post-execution metadata-only
   repair added the canonical governance fields while preserving the original primary
   metric, nulls, failure predicate, intervention, and no-promotion boundary. The
   original record remains in Git history at `1992c58`; the repair is disclosed in
   `research/governance/CSCA-05-H4-SCHEMA-REPAIR.md`.
3. The historical ACT-R&D-01 execution gate assumed the S01 reproduction queue must
   forever contain `MATCHED_BUDGET_ESTIMATOR_PENDING`. After independently sealed
   CSCA-03R/CSCA-05 evidence advanced the queue, that stale literal became a false
   failure. The gate was de-drifted to preserve the real authority boundaries
   (`PRIMARY_SOURCE_BYTES_QUARANTINED`, `PAPER_REPRODUCTION_PENDING`) while permitting
   the controlled estimator qualification state.

None of these repairs changes confirmatory data, thresholds, cohort membership, or
scientific verdicts.

## Final machine verification

PASS:

- `scripts/csca05_gate.py`
- `scripts/csca04_gate.py`
- `scripts/csca03r_gate.py`
- `scripts/rd03_gate.py`
- `scripts/research_ops_gate.py`
- `scripts/research_execution_gate.py`
- `scripts/research_ingestion_gate.py`
- `scripts/causal_debt_gate.py`
- `scripts/via_gate.py`
- `scripts/architecture_gate.py`
- `scripts/hermeticity_gate.py`
- `scripts/complexity_gate.py`
- `scripts/inference_integrity_gate.py`
- `scripts/doc_status_gate.py`
- `scripts/verdict_binding_gate.py`
- `scripts/technical_quality_gate.py`
- `scripts/truth_gate.py`

Focused research-operations suite:

`44 passed in 8.06s`.

Full collection:

`406 tests collected in 3.55s`, with zero collection errors.

A full behavioral `python -m pytest -q` run was attempted but exceeded the available
300-second execution window after reaching 17% of the suite. Therefore this record
does **not** claim a full-suite behavioral PASS.

## Evidence integrity

`artifacts/csca-05-runtime/SHA256SUMS` binds 144 result/checkpoint/trace/diagnostic
files. The ledger was independently re-read and all 144 SHA-256 values matched.

## Physical-compute boundary

The execution environment exposes CPU PyTorch only; CUDA is unavailable. CPU latency
measurements are authoritative for this container, while GPU time, GPU VRAM, energy,
and production throughput remain `NOT_MEASURED` / unqualified.
