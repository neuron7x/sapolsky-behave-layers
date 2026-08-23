# DGC Evidence Closure Executor v1

Status: engineering control; **not empirical evidence**.

## Purpose

Turn the external-evidence runbook into a fail-closed, source-bound stage ledger. The executor prevents four classes of invalid promotion:

1. stage skipping;
2. evidence-file substitution after a stage is frozen;
3. repository commit/tree drift across one evidence generation;
4. command failure being recorded as a successful transition.

The stage chain is:

`SOURCE_VERIFIED -> MATERIALIZED_VERIFIED -> HARNESS_FROZEN -> B2_FITTED -> TRIAL_SIZED -> GENERATION_ROOT_FROZEN -> CONFIRMATORY_EXECUTED -> P9_SUPPORTED -> GENERALIZATION_SUPPORTED -> INDEPENDENT_REPLICATION_SUPPORTED -> P19_SEALED -> PRODUCT_QUALIFIED`.

Every transition binds an exact SHA-256 for every evidence artifact and chains the new receipt to the previous receipt digest. The ledger derives `product_qualified`; callers cannot set it directly.

## Boundary

This control does **not** decide that an experiment, benchmark, statistical method, theorem or client result is valid. Those judgments remain in the stage-specific frozen gates. Presence of a receipt proves only that the declared command(s) returned success and the declared evidence bytes matched their frozen identities.

## Research handoff transport

`scripts/make_dgc_research_handoff.py` exports blobs directly from a Git commit rather than from the working tree. This eliminates the failure mode where a handoff advertises a new HEAD while packaging stale source bytes. Archive metadata is normalized; double builds at one Git object are byte-reproducible. The emitted artifact is explicitly non-promoting (`product_qualified=false`).
