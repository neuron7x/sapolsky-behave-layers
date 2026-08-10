# CSCA-06C-R1 — Position/Content Causal Disentanglement

**Date:** 2026-08-10  
**Final verdict:** `POSITION_CONTENT_MECHANISM_UNRESOLVED`  
**Content-specific causal credit:** NOT SUPPORTED  
**Position/locality mechanism promotion:** BLOCKED by independent-replication coverage.

## Why this gate exists

CSCA-06B produced perfect agreement across two declared stochastic soft-intervention kernels, but all 96 confirmatory robust cases selected `A_RECENT`. Operator robustness therefore did not distinguish a cognitive-content mechanism from the simpler fact that the last bytes before an autoregressive prediction boundary are usually the most causally influential.

CSCA-06C attacks that confound directly.

## Intervention

For each fresh base prompt, the four original 4-byte candidate contents were cyclically rotated through all four fixed positions. Thus every original content identity occupied `A_RECENT`, `B_PREV`, `C_MIDDLE` and `D_EARLY` exactly once.

The target token was frozen from the unpermuted base prompt and held constant across all four rotations. Therefore the outcome was not silently redefined after moving content.

The two CSCA-06B donor-resampling intervention kernels were retained. Exact finite-kernel Shapley was used; no learned estimator was involved. Donor assignments were held fixed across rotations of the same base prompt.

## Provenance incidents and fail-closed handling

The original `CSCA-06C-PC` namespace was burned after a performance smoke test accidentally exposed one would-be PRIMARY prompt's boolean `fully_resolved=False` state. No credit vector or aggregate was observed, but the entire namespace was nevertheless invalidated. `CSCA-06C-R1` received fresh prompt hashes and a separate preregistration.

R1's long-lived CPU execution then repeatedly exceeded the runtime window without writing result artifacts. The implementation was changed only in physical scheduling: exact coalition×donor sums were batched, CPU thread counts pinned, and finally the cohort was executed as hermetic four-prompt shards. Every shard reloaded the frozen checkpoint and checked model-state nonmutation. Scientific definitions and thresholds were never changed.

## PRIMARY

24 fresh base prompts: 12 PROSE + 12 CODE. Zero overlap with all prior CSCA-05/06B prompt hashes.

Fully resolved under all four rotations and both operator kernels:

- PROSE: `8/12 = 0.6666667`;
- CODE: `8/12 = 0.6666667`;
- pooled: `16/24 = 0.6666667`.

Among every fully resolved case:

`PositionTracking = 1.0`

`ContentTracking = 0.25`

All 16 baseline top positions were `A_RECENT`.

Thus PRIMARY satisfies the preregistered **position/locality** pattern and fails the content-specific pattern.

## Independent REPLICATION

24 new base prompts on the independently trained replication checkpoint:

- PROSE fully resolved: `4/12 = 0.3333333`;
- CODE: `7/12 = 0.5833333`;
- pooled: `11/24 = 0.4583333`.

For every fully resolved replication case again:

`PositionTracking = 1.0`

`ContentTracking = 0.25`.

All 11 baseline top positions were again `A_RECENT`.

However the preregistered minimum fully-resolved fraction was `0.50` in every stratum. PROSE and pooled replication therefore fail before a position/locality mechanism may be promoted.

Replication thresholds were not weakened after observing the pattern.

## Interpretation

The desired content-specific mechanism receives no support. Wherever the intervention-family comparison is resolved, causal credit follows the **fixed recent position**, not the same 4-byte content as that content is moved through the prompt.

This is strong evidence against interpreting the current byte-level shadow credit as a content identity mechanism on this benchmark.

But the stronger statement — "position/locality is a qualified replicated mechanism" — is also withheld. The replication operator-family resolution surface is too sparse under the frozen margin: only 4/12 PROSE and 11/24 pooled base prompts satisfy the all-rotation prerequisite.

Therefore the scientifically correct result is neither a rescued cognitive-content positive nor an overclaimed recency theorem:

`POSITION_CONTENT_MECHANISM_UNRESOLVED`.

## Architectural consequence

Do **not** train an amortized causal-credit student on CSCA-05/06B labels yet. It would predominantly learn the already obvious autoregressive locality structure and could reproduce it cheaply without demonstrating the intended cognitive mechanism.

The next admissible step must create a benchmark/intervention where content identity and token distance are independently manipulable while operator-family support remains non-degenerate. Until then:

- semantic causal authority: BLOCKED;
- student/amortization: BLOCKED;
- replay control: BLOCKED;
- active causal control: BLOCKED.
