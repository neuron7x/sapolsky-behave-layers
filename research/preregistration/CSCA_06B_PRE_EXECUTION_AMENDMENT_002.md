# CSCA-06B-OP — Pre-execution Amendment 002

**Date:** 2026-08-10  
**Observed scientific data before amendment:** NONE.  
**Trigger:** the first post-hermetic calibration attempt exceeded the 300-second execution window before producing any result artifact. No calibration row, delta, credit vector, or outcome was written.

## Change

Vectorize the eight frozen donor realizations for each coalition into one model batch. The mathematical intervention game is unchanged: every one of the same eight prompts is evaluated and the same arithmetic mean of `log P(y*)` defines `v_K(S)`.

The implementation now records separately:

- logical intervention realizations evaluated;
- physical model batch calls.

## Unchanged

No prompt, donor hash, donor count, kernel, checkpoint, calibration rule, threshold, metric, cohort, or authority rule changes. This amendment changes only execution scheduling of an identical deterministic finite sum.
