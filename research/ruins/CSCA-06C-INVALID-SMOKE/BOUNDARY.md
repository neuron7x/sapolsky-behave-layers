# CSCA-06C-PC — Invalid Smoke Exposure Boundary

**Status:** `INSTRUMENT_PROVENANCE_INVALID_SMOKE_EXPOSURE`  
**Date:** 2026-08-10

After the first full PRIMARY attempt timed out without writing artifacts, the exact-game batching repair was smoke-tested on **one** would-be PRIMARY PROSE prompt before that repair was committed. The console exposed only:

`fully_resolved = False`, `position_tracking = None`, `content_tracking = None`, `physical_model_batch_calls = 9`.

No credit vector, candidate identity, threshold change, cohort aggregate, or replication result was observed or written.

Nevertheless, the intended PRIMARY namespace is scientifically contaminated. Fail-closed action:

- original experiment ID `CSCA-06C-PC` is not allowed to produce an authoritative confirmatory verdict;
- all would-be `CSCA06C:PROMPT:*` confirmatory prompt namespaces are burned, including unobserved members;
- thresholds and mechanism definitions are not changed;
- a new experiment ID `CSCA-06C-R1` uses a new `CSCA06C-R1` prompt namespace for both PRIMARY and REPLICATION;
- this invalid smoke observation has no claim authority and cannot be used to tune the R1 design.
