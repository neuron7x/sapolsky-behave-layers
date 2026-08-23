# DGC Evidence Closure Executor v3

Status: engineering/research control; **not empirical product evidence**.

## Purpose

Turn the external-evidence runbook into a fail-closed, source-bound stage ledger and eliminate stale-source, post-hoc-selection, leakage, self-replay and self-consistent-forgery failure modes. A coded transition proves only that the declared validator accepted the bound bytes under its explicit assumptions; it never substitutes for the external observation required by that stage.

## Canonical stage chain

`SOURCE_VERIFIED -> MATERIALIZED_VERIFIED -> EXECUTION_MANIFESTS_FROZEN -> CCF_SPEC_FROZEN -> GENERALIZATION_REGISTRY_FROZEN -> B2_FITTED -> HARNESS_FROZEN -> TRIAL_SIZED -> GENERATION_ROOT_FROZEN -> CONFIRMATORY_EXECUTED -> P9_SUPPORTED -> GENERALIZATION_SUPPORTED -> INDEPENDENT_REPLICATION_SUPPORTED -> P19_SEALED -> PRODUCT_QUALIFIED`.

The ordering is intentional:

- non-baseline execution identities are frozen before outcome-bearing calibration;
- CCF quantization/oracle semantics are frozen before outcomes;
- G1-G5 evaluation identities are frozen before B2/confirmatory outcomes;
- B2 is fitted only on calibration tasks;
- the final B0-B3+DGC harness is frozen only after the fitted B2 identity exists;
- replication occurs only after primary P9 and preregistered G1-G5 scientific gates pass.

## Materialization authority

`MATERIALIZED_VERIFIED` is not granted by a receipt declaration. Import re-verifies the published generation:

- SWE-bench parquet bytes are checked against the frozen SHA-256 and task population, then the workload seal and materialized authority are recomputed;
- Terminal-Bench repository/task/dataset Git SHA-1 object identities are reconstructed directly from published bytes and POSIX executable/symlink modes after `.git` metadata has been removed;
- canonical `SOURCE_VERIFIED` authority is reconstructed from the repository source registry;
- `MATERIALIZED_VERIFIED` authority must equal `promote_materialized_verified(canonical_source_authority, recomputed_seal)`;
- generation registry/materializer digests must match the exact DGC repository tree.

A self-consistent forged generation is therefore insufficient for promotion.

## Three-way task partition

The primary workload is partitioned deterministically before outcomes into three disjoint populations:

1. calibration tasks;
2. primary confirmatory tasks;
3. G1 unseen-task holdout.

The verifier reconstructs the split from the union task population and frozen fractions. A self-consistent but differently allocated partition is rejected.

B2 V2 requires examples to cover the exact calibration population and forbids both primary-confirmatory and G1 populations.

## Execution, CCF and G1-G5 preregistration

`EXECUTION_MANIFESTS_FROZEN` content-addresses and semantically validates model, prompt, tools, environment/container digest, hard budget, pricing snapshot, scorer, statistical plan and the five governance-policy arms. Mutable aliases and non-digest container tags are rejected.

`CCF_SPEC_FROZEN` binds the exact quantizer implementation and counterfactual-oracle semantics before outcomes.

`GENERALIZATION_REGISTRY_FROZEN` binds exact G1-G5 definitions before B2:

- G1 unseen tasks;
- G2 unseen domain;
- G3 changed model/provider;
- G4 changed economics/pricing;
- G5 perturbation shift.

The registry binds B0/B1/B2/B3/DGC semantic roles to the baseline-panel SSOT, the source/materialization identities for each axis, the paired-randomness semantics and no-retuning rule.

## B2 and final harness

`B2_FITTED` requires exact calibration-only coverage, exact forbidden downstream populations and deterministic fit-receipt recomputation.

`HARNESS_FROZEN` binds an executable-frozen B0-B3 panel containing the authorized fitted B2 model and exactly five policy arms. All arms share one controlled-comparison frame and differ only in governance policy identity.

## Trial sizing boundary

Cluster-aware sizing remains a conservative **planning authority**, not the final inference theorem. It is useful for task-superpopulation/resource reasoning and prevents within-task repeats from being represented as new task diversity.

A separate empirical-Bernstein planning solver estimates the repetition count needed for a target confidence width using a calibration variance proxy. Its unbiased sample-variance ceiling is `L^2/2` when calibration sample size is not supplied; Popoviciu's `L^2/4` population ceiling is not incorrectly applied to an `n-1` sample variance.

Both sizing systems remain planning-only. Final statistical promotion is recomputed from observed confirmatory data.

## Confirmatory execution authority

The confirmatory subject must contain the complete frozen `task × policy × replicate` population, replayable result/evidence bytes, physical-cost evidence and coordinator audit chain. Missing, duplicate, quarantined, substituted or extra work units prevent `CONFIRMATORY_EXECUTED`.

## P9 statistical authority

P9 deliberately keeps two evidence statements separate.

### Exact frozen-panel fact

`EXACT_FROZEN_FINITE_PANEL_PARETO_V1` deterministically checks the complete executed paired panel against every B0-B3 baseline:

- mean physical cost gain `baseline - DGC > 0`;
- mean quality gain `DGC - baseline >= -quality_margin`;
- mean catastrophic-regret gain `baseline - DGC >= -catastrophic_margin`.

This statement contains no probability or generalization semantics.

### Conditional bounded expected-effect support

`MAURER_PONTIL_THEOREM_11_EMPIRICAL_BERNSTEIN_LOWER_V1` uses the full paired `task × replicate` population and variance-sensitive one-sided empirical-Bernstein lower bounds. The confidence statement is explicitly conditional on the frozen cross-pair provider stochastic-independence assumption.

The machine verifies paired seed schedules, unique provider request IDs and complete paired coverage. It does not claim to prove provider-internal stochastic independence; `randomness_assumption_verified=false` remains explicit unless external evidence establishes more.

### P9 stage semantics

`P9_SUPPORTED` requires **all** of:

- exact-panel success;
- empirical-Bernstein lower-bound success under the frozen assumption;
- complete ten-component physical-cost accounting;
- exact multiplicity allocation;
- complete CCF headroom audit;
- raw-subject replay and lineage equality.

Neither component can rescue the other. A favorable exact point estimate with a failed confidence bound is not `P9_SUPPORTED`, and a confidence procedure cannot rescue an unfavorable exact panel.

See `docs/DGC_PRODUCT_STATISTICAL_PLAN_v3.md` and `docs/DGC_STATISTICAL_AUTHORITY_V3.md`.

## G1-G5 scientific authority

Each G1-G5 axis uses the same exact + bounded-inference conjunction:

- exact frozen-axis panel result;
- empirical-Bernstein lower-bound result under frozen randomness assumptions;
- materialized source authority replay;
- exact five policy arms, tasks and repetitions;
- full physical-cost evidence;
- no policy retuning.

`GENERALIZATION_SUPPORTED` requires both evidence components on **every** preregistered G1-G5 axis. This supports only those five frozen shift panels and is not a universal-generalization statement.

## Independent replication authority

The old replication boolean contract is not used for stage promotion.

`INDEPENDENT_REPLICATION_SUPPORTED` requires a fresh external replay of the primary P9 core package after primary P9 + G1-G5 support:

1. the same frozen harness, confirmatory task identity, statistical plan and CCF spec;
2. a newly recomputed raw execution/physical-cost/CCF subject;
3. a replica P9 scientific PASS under the same frozen assumptions;
4. fresh execution population, execution bundle, physical-cost population and CCF-evidence population digests distinct from the primary run;
5. a canonical external attestation signed through `ssh-keygen -Y` under namespace `dgc-independent-replication-v1`;
6. the signature receipt binds the attestation, signature, allowed-signers file and exact `ssh-keygen` executable bytes.

The signed attestation states unchanged methodology, no author control over execution/result selection and raw-result disclosure.

Important claim boundary:

- cryptographic signature possession is machine-verifiable;
- fresh execution provenance is machine-verifiable;
- methodology identity is machine-verifiable;
- the social truth of the signer's independence is **externally attested, not machine-proven**.

Therefore every replication authority must keep `social_independence_machine_proven=false`. The system refuses to convert a social assertion into a fake technical proof.

## Research handoff transport

`scripts/make_dgc_research_handoff.py` exports blobs directly from a Git commit rather than from the mutable working tree. This prevents a handoff from advertising a new HEAD while packaging stale source bytes.

## Claim boundary

None of these controls establish a real external effect until the frozen workloads are actually materialized and executed. They do not establish universal superiority, customer economics, production safety or production control authority.

`PRODUCT_QUALIFIED=false` remains mandatory until the real external chain, signed fresh replication, P19 sealing and downstream operational gates are actually satisfied.
