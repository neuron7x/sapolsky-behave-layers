# CSCA-06C-R1 — Execution Amendment 002: Hermetic Sharding

**Date:** 2026-08-10  
**Authoritative R1 scientific output observed before amendment:** NONE.

Even with deterministic one-thread CPU scheduling, the monolithic cohort process repeatedly exceeded the execution window after several base-prompt evaluations without writing a cohort artifact. Isolated calibration diagnostics showed each base prompt completes deterministically in about a few seconds, while the long-lived process is subject to environment-level throughput stalls.

## Change

Execute the frozen cohort as hermetic shards of four base prompts:

`cohort × context × shard(start={0,4,8}, count=4)`.

Each shard:

1. loads the same frozen checkpoint;
2. evaluates exactly the same prompt hashes, four rotations, two kernels, 16 coalitions and eight donor assignments;
3. records model-state hash before/after;
4. writes rows without computing a scientific cohort verdict.

A separate deterministic aggregator refuses to run unless all expected shards exist, prompt indices are complete/unique, all shard model-state checks pass, and prior-prompt overlap is zero. It then computes exactly the preregistered cohort metrics and decision.

## Scientific invariance

No scientific datum, threshold, prompt, donor, target, model, intervention, or decision rule changes. Sharding is only process isolation for the same finite deterministic computation.
