# CSCA-06C-PC — Position/Content Causal Disentanglement

**Status:** PREREGISTERED BEFORE EXECUTION  
**Parent:** `CSCA-06B-OP = OPERATOR_FAMILY_ROBUSTNESS_QUALIFIED_NARROWED`  
**Trigger:** CSCA-06B produced 96/96 robust confirmatory cases across PRIMARY+REPLICATION, but every one selected `A_RECENT`; robust non-recent count was zero.

## Kill question

Is the real-model direct-intervention credit attached to **content identity**, or can the simpler autoregressive position/locality explanation account for it?

## Core manipulation

For each fresh base prompt, preserve all non-candidate bytes and cyclically permute the four original 4-byte candidate blocks across the four fixed positions:

`A_RECENT, B_PREV, C_MIDDLE, D_EARLY`.

Use exactly four rotations so each original content block occupies every candidate position once.

The next-token target is frozen from the unpermuted base prompt:

`y*_base = argmax P(next_token | base_prompt)`.

Every rotated intervention game measures support/inhibition of this **same target token**. The outcome is therefore not silently redefined after moving content.

## Intervention-family control

Reuse the two CSCA-06B admissible stochastic soft-intervention families:

- `K_TRAIN_CONTIG8`;
- `K_COHORT_CONTIG8`.

For a base prompt, donor assignments are frozen from the base prompt identity and shared across all four rotations. Donor spans are required not to equal any of the four candidate content blocks, so changing the content-position permutation does not change the finite donor set.

Use exact Shapley of the exact finite-kernel expected game. No learned or finite-Shapley estimator is admitted.

The CSCA-06B frozen resolution margin `delta=0.25` is inherited without recalibration.

## Fresh units

- PRIMARY: 12 fresh PROSE + 12 fresh CODE prompts under a new `CSCA06C` hash namespace;
- REPLICATION: 12 fresh PROSE + 12 fresh CODE prompts under the same frozen generator and independent CSCA-05 replication checkpoint.

Prompt hashes must have zero overlap with CSCA-05 and CSCA-06B prompt units.

## Per-rotation admissibility

A rotation is usable only when both operator kernels agree on top candidate and sign and satisfy the inherited `delta` margin/magnitude conditions from CSCA-06B.

A base prompt is `FULLY_RESOLVED` only if all four rotations are usable. Otherwise it contributes only to abstention/coverage statistics and not to position-vs-content tracking.

## Tracking estimands

For a fully resolved base prompt:

- `p0` = robust top **position** at rotation 0;
- `c0` = original content identity occupying `p0` at rotation 0.

Across four rotations:

`PositionTracking = mean[ top_position_r == p0 ]`

`ContentTracking = mean[ content_identity_at(top_position_r,r) == c0 ]`.

If credit follows the moved content, ContentTracking should dominate. If it follows the fixed locality role, PositionTracking should dominate.

## Frozen decision rules

Evaluate pooled, PROSE and CODE separately in PRIMARY and REPLICATION.

Minimum usable surface:

`FULLY_RESOLVED_PROMPT_FRACTION >= 0.50`.

`CONTENT_SPECIFIC_CAUSAL_CREDIT_QUALIFIED_NARROWED` requires in **every** stratum and both cohorts:

- `ContentTracking >= 0.75`;
- `ContentTracking - PositionTracking >= 0.25`.

`POSITION_LOCALITY_EXPLANATION_SUPPORTED_NARROWED` requires in **every** stratum and both cohorts:

- `PositionTracking >= 0.90`;
- `PositionTracking - ContentTracking >= 0.50`.

If neither conjunction survives, verdict is `POSITION_CONTENT_MECHANISM_UNRESOLVED`.

PRIMARY failure cannot be rescued by REPLICATION.

## Noninterference

No generation output is controlled. Model state before/after must be identical. No logits, weights, sampling settings, replay priorities or token generation are modified by the result.

## Interpretation boundary

Even a content-tracking positive would establish only content-position invariance for `THIS MODEL × THESE BYTE BLOCKS × THESE STOCHASTIC INTERVENTIONS × THIS FIXED MODEL-INTERNAL TARGET`. It would not establish semantic, linguistic, human or biological causality.

A position-tracking result is not a failure of direct causal measurement. It means the measured causal mechanism is simpler than the desired cognitive-content interpretation and blocks student/replay promotion on this benchmark.
