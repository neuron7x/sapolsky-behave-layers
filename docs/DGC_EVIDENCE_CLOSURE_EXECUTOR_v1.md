# DGC Evidence Closure Executor v5

Status: **engineering/research control; not empirical product evidence**.

This is the current operational SSOT for DGC evidence closure. A coded transition proves only that exact bound subjects passed the declared verifier under its explicit theorem/engineering assumptions. It never substitutes for the external observation required by that stage.

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

The order is evidence, not presentation. Statistical method, CCF, G1–G5, fault semantics, verifier plan and verifier trust policy must be frozen before outcome-bearing execution. B2 is calibration-only. Downstream evidence cannot redefine the method after seeing confirmatory outcomes.

## 2. `T_exec`: immutable execution source identity

Every scientific stage in one generation is bound to one clean Git commit/tree:

```text
T_exec = (repo_commit, repo_tree)
```

`_assert_repository_identity()` requires HEAD/tree to equal the ledger identity and requires a clean tracked working tree. Outcome-bearing execution is therefore not permitted while executable/statistical/scorer/policy/methodology source is moving.

## 3. Materialization and partition

`MATERIALIZED_VERIFIED` is recomputed from frozen external source authority and actual materialized bytes. A self-consistent receipt is insufficient.

Primary tasks are deterministically split before outcomes into pairwise-disjoint:

1. calibration;
2. primary confirmatory;
3. G1 unseen-task holdout.

B2 may use only calibration examples and must explicitly forbid both downstream populations.

## 4. Pre-outcome freeze

Before B2/confirmatory outcomes the generation freezes:

- execution manifests;
- model/prompt/tools/environment/container identities;
- budget and pricing snapshot;
- scorer and statistical plan;
- CCF semantics;
- G1–G5 registry and no-retuning rule;
- fault-injection matrix;
- P19 external verification plan;
- P19 verifier trust policy.

The final B0/B1/B2/B3/DGC harness is frozen after the fitted B2 identity exists and before confirmatory execution.

## 5. Trial sizing versus final inference

Cluster-aware sizing and empirical-Bernstein width planning are **planning authorities only**. They may estimate required resources from calibration evidence; they cannot authorize P9.

Current final primary inference is V5.1:

1. exact frozen-panel fact; and
2. anytime-valid average-conditional-mean inference using Howard–Ramdas–McAuliffe–Sekhon Theorem 4 with exact polynomial-stitching Eq. (10).

The primary target is the precommitted bounded adapted sequence average conditional mean, not an iid population mean. Provider-request independence is not a primary validity assumption.

V5.1 also freezes the exact binary64 `zeta(1.4)` reference value and boundary-parameter digest. Historical V4/V5 generations cannot authorize current promotion.

## 6. Confirmatory/P9 contract

`CONFIRMATORY_EXECUTED` requires the complete frozen `task × policy × replicate` population, replayable result/evidence bytes, coordinator audit chain and physical-cost subjects.

`P9_SUPPORTED` requires all of:

- exact-panel cost/quality/regret conditions against B0–B3;
- V5.1 anytime lower-bound support;
- exact paired population coverage;
- ten-component physical-cost verification;
- frozen multiplicity allocation;
- CCF audit completeness;
- raw-subject and lineage replay.

A favorable point estimate cannot rescue a failed confidence gate, and the confidence procedure cannot rescue an unfavorable exact panel.

Primary multiplicity is frozen across:

```text
2 workload families × 4 baselines × 3 endpoints = 24 claims
```

## 7. G1–G5

Each G-axis requires exact shift-panel evidence plus V5.1 anytime support, exact source/model/pricing/perturbation identity, five policy arms, physical-cost evidence and no retuning.

Per workload family:

```text
5 axes × 4 baselines × 3 endpoints = 60 claims
family FWER = 0.05
```

`GENERALIZATION_SUPPORTED` means support on the five preregistered shifts only. It is not a universal-generalization claim.

The final two-family product claim uses an explicit intersection–union AND composition.

## 8. Fault tolerance

`FAULT_TOLERANCE_SUPPORTED` is not a boolean chaos-test declaration.

Each frozen fault class requires typed injection evidence, raw artifact binding, state-transition evidence and an evidence-bound audit event. Complete case coverage, no unauthorized promotion, no budget bypass and no duplicate side-effect commit are required.

## 9. Independent replication

Independent replication requires the same frozen methodology but fresh:

- execution/result population;
- physical-cost population;
- CCF population;
- scientific P9 result;
- externally signed replication attestation.

Fresh subject identity and signature possession are machine-verifiable. Social independence is externally attested, never machine-proven:

```text
social_independence_machine_proven = false
```

## 10. Family P19

Each canonical workload family receives its own P19 evidence root. One family cannot authorize the global product claim.

Required families are exactly:

```text
SWE_BENCH_VERIFIED
TERMINAL_BENCH_2_1
```

Each P19 seals stage evidence, methodology anchors and disclosed raw subject roots.

## 11. External P19 semantic replay

For each family, external verification uses one frozen plan with eight checks:

1. repository identity;
2. theorem/statistical-plan identity;
3. subject-root rehash;
4. P19 seal rebuild;
5. primary P9 raw replay;
6. G1–G5 raw replay;
7. fault-tolerance raw replay;
8. independent-replication raw replay.

Each check discloses and binds:

- canonical check receipt;
- stdout bytes;
- stderr bytes;
- replay evidence bytes.

The final verification report also binds the frozen verification plan and exact verifier entrypoint.

## 12. Frozen external trust

`P19_VERIFIER_TRUST_POLICY_V2` is not caller-supplied at terminal promotion. It requires at least two distinct verifier principals and at least two distinct SSH key materials; one key aliased under two principal names cannot satisfy verifier separation.

The current canonical trust policy is not activated with real external verifier keys, so product qualification remains fail-closed.

## 13. Global V5 portable product authority

Current terminal product authority is:

```text
DGC_GLOBAL_PRODUCT_QUALIFICATION_AUTHORITY_V5
```

Global V5 validates the complete two-family evidence chain and SSH signatures but separates two concepts:

### Portable cryptographic truth

Product authority binds:

- P19 digest;
- verifier principal;
- attestation SHA-256;
- verification-report SHA-256;
- signature SHA-256;
- frozen allowed-signers SHA-256;
- SSH namespace;
- `signature_verified=true`.

### Environment-specific verification provenance

The local `ssh-keygen` path, binary SHA and verifier stdout/stderr are useful forensic execution provenance but are **not** part of the portable Global V5 authority digest.

Therefore two machines verifying the same signature inputs may produce different tool-execution receipts but must derive the same portable Global V5 scientific authority.

Global V4 remains a validation component/historical implementation layer; it is not the current terminal release authority.

## 14. Pointer V3

Current terminal replay index:

```text
artifacts/dgc-product-v1/PRODUCT_QUALIFICATION_POINTER_V3.json
```

Pointer V3 does not trust a standalone green Global V5 document. It:

- rehashes the terminal ledger and Global V5 bytes;
- resolves both P19 roots;
- resolves both reports/attestations/signatures;
- resolves the frozen verifier policy;
- rebuilds Global V5 semantically;
- requires the terminal `PRODUCT_QUALIFIED` ledger receipt to bind that exact Global V5 artifact.

The canonical Pointer V3 is currently:

```text
activation_authorized = false
product_qualified_claimed = false
```

## 15. `T_pkg`: post-outcome packaging identity

Scientific closure ends under `T_exec`. Evidence packaging happens later under descendant revision `T_pkg`.

Canonical lifecycle:

```text
freeze method + verification plan + trust policy
→ commit T_exec
→ execute and close scientific stages while HEAD stays T_exec
→ external replay + signatures
→ Global V5
→ ledger reaches PRODUCT_QUALIFIED under T_exec
→ create T_pkg
→ add disclosed evidence + activate Pointer V3
→ verify T_exec is ancestor of T_pkg
→ verify append-only delta
→ derive graph-complete bundle
→ deterministic double-build release
```

`DGC_EVIDENCE_PACKAGING_AUTHORITY_V2` rejects post-outcome source/methodology/verifier-plan mutation, deletion, mode changes, symlink/special Git objects and ambiguous paths.

## 16. Qualified evidence bundle V4

Current graph authority:

```text
DGC_QUALIFIED_EVIDENCE_BUNDLE_AUTHORITY_V4
```

It derives required release subjects from the actual Pointer/P19/Global-V5 graph, including:

- ledger;
- Global V5;
- source registry;
- verifier policy and trust store;
- both P19 roots;
- stage evidence;
- methodology anchors;
- raw subject roots;
- reports/attestations/signatures;
- frozen verification plan;
- verifier entrypoint;
- all check receipts/stdout/stderr/evidence.

Every required file must be either:

1. `EXECUTION_SOURCE_T0` — identical Git blob in `T_exec` and `T_pkg`; or
2. `PACKAGING_EVIDENCE_T1` — approved append-only evidence tracked in `T_pkg`.

Untracked evidence, omitted transcript vertices, mutated source anchors or post-hoc files outside evidence namespaces fail closed.

## 17. Deterministic release V6

Current release manifest schema:

```text
DGC_DETERMINISTIC_RESEARCH_RELEASE_V6
```

Qualified release contains separate archive roles:

- `dgc-execution-source-<T_exec>.tar.gz` from immutable Git objects with normalized metadata;
- `dgc-packaging-evidence-<T_pkg>.tar.gz` from tracked evidence namespaces;
- packaging authority;
- qualified bundle authority;
- release manifest;
- `SHA256SUMS`.

Product-tag release executes the **product-qualified build twice** and requires byte-identical outputs.

No SLSA conformance level is claimed:

```text
slsa_conformance_claim = false
```

## 18. Product is not production

Even valid product qualification does not establish production control authority. Production-provider traces, shadow mode, bounded canary, sustained monitoring and applicable operational/client evidence remain separate obligations.

```text
PRODUCT_QUALIFIED != PRODUCTION_CONTROL_AUTHORIZED
```

## 19. Current truth

The external empirical campaign has not been completed. Real P9, G1–G5, fault campaign, independent replication, two real P19 roots and external P19 signatures remain empirical obligations.

Current mandatory truth:

```text
PRODUCT_QUALIFIED = false
PRODUCTION_CONTROL_AUTHORIZED = false
```

Current mathematical SSOT:

- `artifacts/dgc-product-v1/PREREGISTRATION.md`
- `docs/DGC_PRODUCT_STATISTICAL_PLAN_v5.md`
- `docs/DGC_STATISTICAL_AUTHORITY_v5.md`
- `docs/DGC_THEOREM_AUDIT_v5.md`

Release provenance SSOT:

- `docs/DGC_RELEASE_PROVENANCE_v1.md`
