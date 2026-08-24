# DGC Evidence Closure Executor v4

Status: **engineering/research control; not empirical product evidence**.

This document is the current operational map for the DGC evidence-closure branch. A coded transition proves only that the declared validator accepted exact bound subjects under its explicit theorem/engineering assumptions. It never substitutes for the external observation required by that stage.

## 1. Scientific stage chain

```text
SOURCE_VERIFIED
→ MATERIALIZED_VERIFIED
→ EXECUTION_MANIFESTS_FROZEN
→ CCF_SPEC_FROZEN
→ GENERALIZATION_REGISTRY_FROZEN
→ FAULT_INJECTION_SPEC_FROZEN
→ B2_FITTED
→ HARNESS_FROZEN
→ TRIAL_SIZED
→ GENERATION_ROOT_FROZEN
→ CONFIRMATORY_EXECUTED
→ P9_SUPPORTED
→ GENERALIZATION_SUPPORTED
→ FAULT_TOLERANCE_SUPPORTED
→ INDEPENDENT_REPLICATION_SUPPORTED
→ P19_SEALED
→ PRODUCT_QUALIFIED
```

The order is part of the evidence contract. CCF, G1–G5, fault-injection semantics, statistical method and external-verifier trust policy must be frozen before outcome-bearing execution. B2 is calibration-only. Final scientific authorities cannot redefine the method after confirmatory observations exist.

## 2. Immutable execution identity: `T_exec`

Every scientific stage in one generation is bound to one clean Git commit/tree:

```text
T_exec = (repo_commit, repo_tree)
```

`_assert_repository_identity()` requires the checkout HEAD/tree to equal the ledger identity and requires a clean working tree. This is intentional: outcome-bearing execution must not occur while method source is moving.

The post-outcome release/package revision is a different subject and is described in §14.

## 3. Materialization authority

`MATERIALIZED_VERIFIED` is not granted by a receipt declaration.

Import re-verifies the published generation:

- SWE-bench parquet bytes against frozen source SHA/task population, then recomputes workload seal/materialized authority;
- Terminal-Bench Git repository/task/dataset identities from published bytes and Git object semantics;
- canonical `SOURCE_VERIFIED` authority from the repository source registry;
- materialized authority as `promote_materialized_verified(canonical_source_authority, recomputed_seal)`.

A self-consistent forged generation is insufficient.

## 4. Three-way task partition

Before outcomes, the primary workload is deterministically partitioned into three pairwise-disjoint populations:

1. calibration;
2. primary confirmatory;
3. G1 unseen-task holdout.

The verifier re-derives the split from the full task population and frozen fractions. B2 V2 may use only calibration examples and must explicitly forbid both downstream populations.

## 5. Pre-outcome execution/CCF/generalization/fault freeze

`EXECUTION_MANIFESTS_FROZEN` content-addresses and semantically validates model, prompt, tools, environment/container digest, budget, pricing snapshot, scorer, statistical plan and all five governance arms.

`CCF_SPEC_FROZEN` binds the exact quantizer implementation and oracle semantics before outcomes.

`GENERALIZATION_REGISTRY_FROZEN` binds the five no-retuning axes:

- G1 unseen tasks;
- G2 unseen domain;
- G3 changed model/provider;
- G4 changed economics/pricing;
- G5 perturbation shift.

`FAULT_INJECTION_SPEC_FROZEN` binds the required failure matrix before outcomes. Fault tolerance is therefore not allowed to become a post-hoc set of convenient chaos cases.

## 6. B2 and final harness

`B2_FITTED` requires exact calibration-only coverage, exact forbidden downstream populations and deterministic fit-receipt recomputation.

`HARNESS_FROZEN` binds B0/B1/B2/B3/DGC semantic role identities, the authorized fitted B2 model, final confirmatory task identity, scorer/execution manifests and CCF/generalization lineage.

No operator-supplied post-hoc arm relabeling is accepted.

## 7. Trial sizing is planning, not the theorem

Cluster-aware sizing and empirical-Bernstein width planning remain **planning authorities only**.

They may estimate required resources from calibration variance proxies. They do not constitute final scientific evidence and cannot authorize P9.

The final primary statistical gate is V5.1 anytime-valid average-conditional-mean inference plus exact frozen-panel facts.

## 8. Confirmatory execution authority

The confirmatory subject must expose the complete frozen `task × policy × replicate` population plus replayable result/evidence bytes, audit chain and physical-cost subjects.

Missing, duplicate, extra, quarantined or substituted units prevent `CONFIRMATORY_EXECUTED`.

Physical cost is a separate authority domain. Coordinator budget-meter values do not substitute for the ten-component all-in cost certificate used in product economics.

## 9. P9 V5.1 statistical authority

P9 keeps two different propositions separate.

### 9.1 Exact frozen-panel fact

For each B0–B3 baseline and the complete executed panel:

```text
mean(cost_baseline - cost_DGC) > 0
mean(quality_DGC - quality_baseline) >= -quality_margin
mean(regret_baseline - regret_DGC) >= -catastrophic_margin
```

This is deterministic arithmetic about the exact executed panel. It contains no population/generalization probability claim.

### 9.2 Anytime-valid average-conditional-mean evidence

Primary inference uses Howard–Ramdas–McAuliffe–Sekhon Theorem 4 composed with the exact polynomial-stitching Eq. (10) boundary for a bounded adapted sequence.

Target:

```text
(1/t) Σ E[X_i | F_{i-1}]
```

The precommitted order is deterministic. The primary claim does not require iid observations or provider-request independence.

V5.1 pins the exact theorem/runtime identity, including the reference binary64 `zeta(1.4)` value and boundary-parameter digest. Historical V4/V5 generations are retained as archives and cannot authorize current promotion.

Primary multiplicity is frozen across:

```text
2 workload families × 4 baselines × 3 endpoints = 24 claims
```

### 9.3 P9 stage semantics

`P9_SUPPORTED` requires all of:

- exact-panel success;
- V5.1 anytime lower-bound support;
- full paired coverage;
- ten-component physical-cost verification;
- frozen multiplicity allocation;
- CCF audit completeness;
- exact raw-subject/lineage replay.

A favorable point estimate cannot rescue a failed confidence gate and vice versa.

Current math SSOT:

- `artifacts/dgc-product-v1/PREREGISTRATION.md`
- `docs/DGC_PRODUCT_STATISTICAL_PLAN_v5.md`
- `docs/DGC_STATISTICAL_AUTHORITY_v5.md`
- `docs/DGC_THEOREM_AUDIT_v5.md`

## 10. G1–G5 scientific authority

Each axis uses the same claim separation:

- exact frozen shift-panel fact;
- V5.1 anytime average-conditional-mean support;
- exact materialized source/model/pricing/perturbation identity required by that axis;
- exact five-arm population and repetitions;
- physical-cost evidence;
- no retuning.

Per workload family the preregistered G family contains:

```text
5 axes × 4 baselines × 3 endpoints = 60 claims
family FWER = 0.05
```

`GENERALIZATION_SUPPORTED` requires support on every frozen axis. It is evidence for those five defined shifts, not universal generalization.

At the final two-family AND claim, the composition rule is explicitly intersection–union; the per-family G error budget is verified by the Global authority.

## 11. Fault-tolerance authority

`FAULT_TOLERANCE_SUPPORTED` is not a boolean chaos-test declaration.

Each frozen case requires typed injection evidence, raw artifact binding, a state-transition witness and an evidence-bound audit event. Required fault classes include provider/tool/scorer/budget/distributed-control/evidence-corruption failures.

The verifier requires complete case coverage, no unauthorized promotion, no budget bypass, no duplicate side-effect commit and only preregistered safe terminal/recovery outcomes.

## 12. Independent replication

Promotion does not use the legacy boolean replication contract.

Independent replication requires:

- same frozen methodology;
- fresh execution/result population;
- fresh physical-cost population;
- fresh CCF evidence population;
- reproduced scientific P9;
- signed external replication attestation.

Machine-verifiable properties include cryptographic signature possession, fresh subject identities and methodology equality.

The social fact of replicator independence remains externally attested:

```text
social_independence_machine_proven = false
```

The system refuses to convert a social assertion into a fake technical theorem.

## 13. Family P19 and Global V4

Each canonical workload family receives its own P19 evidence root. One family cannot authorize a global product claim.

Global qualification requires exactly:

```text
P19(SWE_BENCH_VERIFIED)
AND
P19(TERMINAL_BENCH_2_1)
```

Both family roots must use the same repository/methodology/statistical theorem identity and must have external semantic-replay attestations.

The external verifier trust store is **not caller-supplied**. `P19_VERIFIER_TRUST_POLICY_V2` is frozen before outcomes and requires at least two distinct verifier principals and at least two distinct signer key materials; one key aliased under two names cannot satisfy the separation rule.

`GLOBAL_PRODUCT_QUALIFICATION_AUTHORITY_V4` binds the Global V3 evidence composition to the frozen trust policy.

`PRODUCT_QUALIFICATION_POINTER_V2` is the terminal replay index. It does not trust a standalone green Global V4 JSON: it rebuilds Global V4 from the disclosed P19/reports/attestations/signatures/policy and checks the terminal ledger receipt.

Current canonical policy/pointer are unconfigured and `activation=false`; therefore product qualification remains unreachable until real external evidence and signer identities exist.

## 14. Post-outcome packaging identity: `T_pkg`

Scientific closure ends under `T_exec`. Evidence packaging happens later under a descendant Git revision `T_pkg`.

Canonical lifecycle:

```text
freeze method/trust policy
→ commit T_exec
→ execute/close all scientific stages while HEAD stays T_exec
→ ledger reaches PRODUCT_QUALIFIED under T_exec
→ create T_pkg
→ add disclosed evidence + activate Pointer V2
→ verify append-only T_exec→T_pkg delta
→ derive graph-complete qualified bundle
→ deterministic double-build release
```

`DGC_EVIDENCE_PACKAGING_AUTHORITY_V1` permits only approved evidence-only additions and exact non-method terminal metadata modifications. It rejects source/methodology mutation, deletion, type/mode changes, symlinks/special objects and ambiguous paths.

`DGC_QUALIFIED_EVIDENCE_BUNDLE_AUTHORITY_V1` derives required release files from the actual Pointer/P19/Global-V4 evidence graph. Every required file must be either:

1. `EXECUTION_SOURCE_T0` — identical Git blob in `T_exec` and `T_pkg`; or
2. `PACKAGING_EVIDENCE_T1` — approved tracked append-only evidence in `T_pkg`.

Untracked raw evidence, mutated source anchors and post-hoc files outside evidence namespaces fail closed.

See `docs/DGC_RELEASE_PROVENANCE_v1.md`.

## 15. Deterministic release

A qualified release has two distinct archive roles:

- `dgc-execution-source-<T_exec>.tar.gz` — generated directly from immutable Git objects with normalized UID/GID/mtime/modes; gitlinks and escaping/absolute symlinks are rejected;
- `dgc-packaging-evidence-<T_pkg>.tar.gz` — tracked evidence/metadata from the packaging revision; symlinks/non-regular files are rejected.

The release also emits:

- `DGC_EVIDENCE_PACKAGING_AUTHORITY.json`;
- `DGC_QUALIFIED_EVIDENCE_BUNDLE_AUTHORITY.json`;
- `DGC_RELEASE_MANIFEST.json`;
- `SHA256SUMS`.

Product-tag release executes the **product-qualified build twice** and requires byte-identical outputs before producing the final artifact.

No SLSA conformance level is claimed:

```text
slsa_conformance_claim = false
```

## 16. Product is not production

Even a valid two-family product-qualified package does not establish production control authority.

Separate downstream obligations remain for production-provider traces, shadow mode, bounded canary, sustained operational monitoring and applicable client/operational evidence.

```text
PRODUCT_QUALIFIED != PRODUCTION_CONTROL_AUTHORIZED
```

## 17. Current claim boundary

None of this control machinery establishes a real effect until the frozen external workloads are actually materialized and executed.

Current mandatory truth remains:

```text
PRODUCT_QUALIFIED = false
PRODUCTION_CONTROL_AUTHORIZED = false
```

Real external P9, G1–G5, fault campaign, independent replication, two P19 roots and external P19 verification remain empirical obligations, not implementation claims.
