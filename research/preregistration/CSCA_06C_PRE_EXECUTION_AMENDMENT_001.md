# CSCA-06C-PC — Pre-execution Amendment 001

**Date:** 2026-08-10  
**Observed scientific data before amendment:** NONE.  
**Trigger:** the first authoritative PRIMARY invocation exceeded the 300-second execution window before writing any result artifact.

## Change

Batch all `16 coalitions × 8 frozen donor realizations = 128` intervention prompts for one `(base prompt, rotation, kernel)` into a single tensor forward, then reconstruct the exact finite-kernel coalition game from the returned log-probabilities before exact Shapley evaluation.

This is an algebraically identical evaluation of the preregistered finite sum. It changes physical scheduling only.

## Unchanged

No prompt, rotation, content mapping, target token, donor byte, kernel, `delta`, decision threshold, cohort, model checkpoint, estimand, or authority boundary changed. The timed-out attempt produced no scientific artifact, and the same PRIMARY prompt namespace remains unexposed at result level.
