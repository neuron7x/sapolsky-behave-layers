# PREREGISTRATION — WP10 De-Circularized Coherence Audit

**Committed before the run.** The audit found coherence "Theorem C" circular: it checks a
hand-encoded table of utility matrices against hand-encoded expected verdicts (`f(x)==f(x)`). This
replaces it with a non-circular check: recompute each claim's certificate `G_lo` from its OWN
committed raw artifact and verify the recorded registry **status agrees with the certificate sign**,
in BOTH directions.

## Design (frozen)

For each certificate-computable claim, recompute `G_lo` (δ=0.05) from committed raw seeds:
- `CWC-L4-plasticity` (positive) — expect `G_lo > 0`, status SUPPORTED_NARROWED.
- `CWC-AC1-compute-identifiability` (positive) — expect `G_lo > 0`, status SUPPORTED.
- `CWC-RD1-real-lm-boundary` (negative) — expect `G_lo <= 0`, status NOT_SUPPORTED.
Assert `status_positive == (G_lo > 0)` for every case.

## Decision rule (FROZEN)

- **COHERENCE_DECIRCULARIZED_0_CONTRADICTIONS** iff 0 contradictions (status sign == certificate
  sign from real artifacts, both directions).
- **COHERENCE_CONTRADICTION** — any mismatch.

## Scope

Meta / rigor. A non-circular coherence check deriving every number from committed evidence. New
claim `CWC-RIGOR4-coherence`.
