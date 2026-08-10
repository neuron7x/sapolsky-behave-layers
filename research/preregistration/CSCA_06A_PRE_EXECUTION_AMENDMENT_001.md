# CSCA-06A Pre-execution Amendment 001

**Date:** 2026-08-10
**Timing:** before any authoritative CSCA-06A calibration/PRIMARY/REPLICATION execution.

A unit test exposed an internal inconsistency in the frozen equivalence control: E0 used beta=0.8 while the nuisance intercept envelope was [-0.75,+0.75], leaving a small nonzero KL instead of exact equivalence. No experimental result had been executed.

Repair: E0 true beta is changed to +0.7, which is exactly absorbable by the already-frozen nuisance intercept envelope under the single available do(X=+1) intervention. All primary structural families, alpha, budgets, nuisance envelope, block design, and confirmatory seed ranges are unchanged.

This amendment strengthens the intended negative control and does not alter any observed result.
