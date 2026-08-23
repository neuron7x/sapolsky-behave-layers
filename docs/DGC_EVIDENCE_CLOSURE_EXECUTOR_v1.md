# DGC Evidence Closure Executor v3

Status: engineering/research control; **not empirical product evidence**.

## Purpose

Turn the external-evidence runbook into a fail-closed, source-bound stage ledger and eliminate stale-source, post-hoc-selection and self-consistent-forgery failure modes. A coded transition proves only that the declared validator accepted the bound bytes under its explicit assumptions; it never substitutes for the external observation required by that stage.

## Canonical stage chain

`SOURCE_VERIFIED -> MATERIALIZED_VERIFIED -> EXECUTION_MANIFESTS_FROZEN -> CCF_SPEC_FROZEN -> GENERALIZATION_REGISTRY_FROZEN -> B2_FITTED -> HARNESS_FROZEN -> TRIAL_SIZED -> GENERATION_ROOT_FROZEN -> CONFIRMATORY_EXECUTED -> P9_SUPPORTED -> GENERALIZATION_SUPPORTED -> INDEPENDENT_REPLICATION_SUPPORTED -> P19_SEALED -> PRODUCT_QUALIFIED`.

The ordering is intentional:

- non-baseline execution identities are frozen before outcome-bearing calibration;
- CCF quantization/oracle semantics are frozen before outcomes, preventing post-hoc oracle tuning;
- G1-G5 evaluation identities are frozen before B2/confirmatory outcomes, preventing post-hoc choice of favorable shift tests;
- B2 is fitted only on the calibration partition;
- the final B0-B3+DGC harness is frozen only after the fitted B2 identity exists.

## Materialization authority

`MATERIALIZED_VERIFIED` is not granted by a receipt declaration. Import re-verifies the published generation:

- SWE-bench parquet bytes are checked against the frozen SHA-256 and task population, then the workload seal and materialized authority are recomputed;
- Terminal-Bench repository/task/dataset Git SHA-1 object identities are reconstructed directly from published bytes and POSIX executable/symlink modes after `.git` metadata has been removed;
- canonical `SOURCE_VERIFIED` authority is reconstructed from the repository source registry;
- `MATERIALIZED_VERIFIED` authority must equal `promote_materialized_verified(canonical_source_authority, recomputed_seal)`;
- generation registry/materializer digests must match the exact current DGC repository tree.

A self-consistent forged generation is therefore insufficient for promotion.

## Three-way task partition

The primary workload is partitioned deterministically before outcomes into three disjoint populations:

1. calibration tasks;
2. primary confirmatory tasks;
3. G1 unseen-task holdout.

The verifier reconstructs the split from the union task population and frozen fractions. A self-consistent but differently allocated partition is rejected.

B2 V2 requires examples to cover the exact calibration population and forbids both the primary confirmatory and G1 holdout populations. This prevents learned-baseline leakage into either downstream evaluation.

## Execution, CCF and G1-G5 preregistration

`EXECUTION_MANIFESTS_FROZEN` content-addresses and semantically validates model, prompt, tools, environment/container digest, hard budget, pricing snapshot, scorer, statistical plan and the five governance-policy arms. Mutable aliases such as `latest` and non-digest container tags are rejected.

`CCF_SPEC_FROZEN` binds the exact quantizer implementation and counterfactual-oracle semantics before outcomes.

`GENERALIZATION_REGISTRY_FROZEN` binds exact G1-G5 definitions before B2:

- G1 unseen tasks;
- G2 unseen domain;
- G3 changed model/provider;
- G4 changed economics/pricing;
- G5 perturbation shift.

The registry also binds the B0/B1/B2/B3/DGC semantic-role mapping to the baseline-panel SSOT and requires no policy retuning.

## B2 and final harness

`B2_FITTED` requires exact calibration-only coverage, exact forbidden downstream task populations and deterministic fit-receipt recomputation.

`HARNESS_FROZEN` binds an executable-frozen B0-B3 panel containing the authorized fitted B2 model and exactly five policy arms: B0, B1, B2, B3 and DGC. All arms share one controlled-comparison frame and differ only in governance policy identity.

## Trial sizing boundary

Cluster-aware sizing remains a conservative **planning authority**, not the final inference theorem. Its variance decomposition prevents repetitions from being mistaken for new task diversity when reasoning about task-superpopulation uncertainty.

Primary P9 is now explicitly a frozen finite-panel estimand. Planning and final inference are therefore kept separate; a calibration-derived variance proxy can size resource needs but cannot manufacture confirmatory support.

## Confirmatory execution authority

The confirmatory subject must contain the complete frozen `task × policy × replicate` population, replayable result/evidence bytes, physical-cost evidence and a coordinator audit chain. Missing, duplicate, quarantined, substituted or extra work units prevent `CONFIRMATORY_EXECUTED`.

## P9 dual statistical authority

P9 separates two claims.

### Exact frozen-panel fact

`EXACT_FROZEN_FINITE_PANEL_PARETO_V1` deterministically checks the complete executed paired panel against all B0-B3 baselines:

- mean physical cost gain `baseline - DGC > 0`;
- mean quality gain `DGC - baseline >= -quality_margin`;
- mean catastrophic-regret gain `baseline - DGC >= -catastrophic_margin`.

This contains no probability or iid/generalization statement.

### Conditional expected-effect evidence

`MAURER_PONTIL_THEOREM_11_EMPIRICAL_BERNSTEIN_LOWER_V1` uses the full paired `task × replicate` population and variance-sensitive one-sided empirical-Bernstein lower bounds. This result is explicitly conditional on the declared cross-pair provider stochastic-independence assumption. The machine verifies the paired seed schedule and unique request identities but does not claim to prove provider-internal independence.

`P9_SUPPORTED` is gated by the unconditional exact-panel result plus complete CCF audit. A conditional empirical-Bernstein PASS cannot rescue an exact-panel FAIL.

See `docs/DGC_STATISTICAL_AUTHORITY_V3.md` for the mathematical contract, multiplicity allocation and assumption boundary.

## G1-G5 dual authority

Each G1-G5 axis uses the same split:

- exact frozen-axis panel result is the stage evidence;
- conditional empirical-Bernstein expected-effect result is retained separately;
- materialized source authority is replayed for the preregistered axis family;
- all five policy arms, all frozen tasks and all repetitions must be present;
- physical operational cost is reconstructed from the complete ten-component evidence boundary;
- policy retuning remains forbidden.

`GENERALIZATION_SUPPORTED` therefore means only that all five **preregistered exact shift panels** passed. It does not mean universal generalization.

## Research handoff transport

`scripts/make_dgc_research_handoff.py` exports blobs directly from a Git commit rather than from the mutable working tree. This eliminates the failure mode where a handoff advertises a new HEAD while packaging stale source bytes. Archive metadata is normalized and the artifact remains explicitly non-promoting.

## Claim boundary

None of these controls establish a real external effect until the frozen workloads are actually materialized and executed. They do not establish universal superiority, independent replication, customer economics, production safety or production control authority.

`PRODUCT_QUALIFIED=false` remains mandatory until the full external chain, independent replication/review, P19 sealing and downstream operational gates are actually satisfied.
