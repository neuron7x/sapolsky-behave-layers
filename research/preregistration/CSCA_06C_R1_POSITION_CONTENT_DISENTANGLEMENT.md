# CSCA-06C-R1 — Position/Content Causal Disentanglement, Clean Rerun

**Status:** PREREGISTERED BEFORE R1 AUTHORITATIVE EXECUTION  
**Parent design:** `CSCA-06C-PC` preregistration.  
**Reason for new ID:** one would-be PRIMARY smoke unit was exposed during a pre-result performance repair; see `research/ruins/CSCA-06C-INVALID-SMOKE/BOUNDARY.md`.

R1 inherits the original scientific protocol **without changing any scientific parameter**:

- 12 fresh PROSE + 12 fresh CODE base prompts per cohort;
- four cyclic content-position rotations;
- fixed original base next-token target across rotations;
- `K_TRAIN_CONTIG8` and `K_COHORT_CONTIG8` exact finite soft-intervention games;
- eight donor assignments per kernel, shared across rotations;
- inherited `delta=0.25`;
- fully-resolved fraction >=0.50;
- content gate: ContentTracking >=0.75 and ContentTracking-PositionTracking >=0.25 in every stratum/cohort;
- position/locality gate: PositionTracking >=0.90 and PositionTracking-ContentTracking >=0.50 in every stratum/cohort;
- no model mutation, no active control, no semantic/replay/student authority.

Only provenance identifiers change:

- experiment ID: `CSCA-06C-R1`;
- prompt namespace: `CSCA06C-R1:PROMPT:{cohort}:{context}:{i}`.

Every R1 prompt hash must be absent from CSCA-05, CSCA-06B and the burned CSCA-06C namespace. PRIMARY and REPLICATION remain separate confirmatory cohorts; replication cannot rescue PRIMARY.
