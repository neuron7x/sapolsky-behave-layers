# DGC Evidence Closure Executor v2

Status: engineering control; **not empirical product evidence**.

## Purpose

Turn the external-evidence runbook into a fail-closed, source-bound stage ledger and eliminate stale-source research handoffs. A coded transition only proves that its declared validator accepted the bound bytes; it does not substitute for the external observation required by that stage.

## Canonical stage chain

`SOURCE_VERIFIED -> MATERIALIZED_VERIFIED -> EXECUTION_MANIFESTS_FROZEN -> B2_FITTED -> HARNESS_FROZEN -> TRIAL_SIZED -> GENERATION_ROOT_FROZEN -> CONFIRMATORY_EXECUTED -> P9_SUPPORTED -> GENERALIZATION_SUPPORTED -> INDEPENDENT_REPLICATION_SUPPORTED -> P19_SEALED -> PRODUCT_QUALIFIED`.

The split between `EXECUTION_MANIFESTS_FROZEN` and `HARNESS_FROZEN` is intentional. The final `FrozenEvaluationHarness` contains `baseline_panel_digest`; B2 calibration changes that digest. Therefore model/prompt/tool/environment/budget/pricing/scorer/statistical-plan/governance identities are frozen before B2, while the final B0-B3+DGC controlled-comparison harness is frozen only after a calibration-only B2 fit has been recomputed and authorized.

## Materialization authority

`MATERIALIZED_VERIFIED` is not granted by a receipt declaration. Import re-verifies the published generation:

- SWE-bench parquet bytes are checked against the frozen SHA-256 and task population, then the workload seal and materialized authority are recomputed;
- Terminal-Bench repository/task/dataset Git SHA-1 object identities are reconstructed directly from published bytes and POSIX executable/symlink modes after `.git` metadata has been removed;
- canonical `SOURCE_VERIFIED` authority is reconstructed from the repository source registry;
- `MATERIALIZED_VERIFIED` authority must equal `promote_materialized_verified(canonical_source_authority, recomputed_seal)`;
- generation registry/materializer digests must match the exact current DGC repository tree.

A self-consistent forged generation is therefore insufficient for promotion.

## Execution manifests and B2 boundary

`EXECUTION_MANIFESTS_FROZEN` content-addresses and semantically validates model, prompt, tools, environment/container digest, hard budget, pricing snapshot, scorer, product statistical plan and the full governance-policy arm set. Mutable aliases such as `latest` and non-digest container tags are rejected.

The calibration/confirmatory task split is deterministic and frozen before outcomes. `B2_FITTED` requires the B2 examples to cover exactly the calibration partition, `forbidden_task_ids` to equal exactly the confirmatory partition, and the declared B2 receipt to equal deterministic recomputation from the bound fit input.

## Final harness authority

`HARNESS_FROZEN` binds an executable-frozen B0-B3 panel containing the authorized fitted B2 model and exactly five policy arms: B0, B1, B2, B3 and DGC. All arms share one comparison frame and differ only in their governance policy digest. It still grants no confirmatory execution or product-promotion authority.

## Research handoff transport

`scripts/make_dgc_research_handoff.py` exports blobs directly from a Git commit rather than from the mutable working tree. This eliminates the failure mode where a handoff advertises a new HEAD while packaging stale source bytes. Archive metadata is normalized and the artifact remains explicitly non-promoting.

## Claim boundary

None of these controls establish real-workload quality non-inferiority, catastrophic-regret non-inferiority, physical cost superiority, generalization, independent replication, customer economics or production safety. `PRODUCT_QUALIFIED=false` remains mandatory until the entire external chain has been observed and verified.
