# CSCA-06C-R1 — Execution Amendment 001

**Date:** 2026-08-10  
**Authoritative R1 scientific output observed before amendment:** NONE.

Two R1 PRIMARY invocations exceeded the execution window before writing a cohort artifact. Profiling on non-authoritative calibration prompts showed intermittent severe CPU-thread scheduling stalls after repeated large batched forwards. No R1 credit vector, tracking metric, or cohort statistic was exposed.

## Change

Force PyTorch intra-op and inter-op CPU thread counts to one inside the CSCA-06C runner.

## Scientific invariance

This changes only deterministic physical scheduling. Model weights, floating-point model function, prompts, target tokens, donor assignments, coalition games, Shapley calculation, thresholds, cohorts and decision rules are unchanged.
