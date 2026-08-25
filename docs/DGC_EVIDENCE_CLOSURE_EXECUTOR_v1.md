# DGC Evidence Closure Executor v7

Status: **engineering/research control; not empirical product evidence**.

This is the current operational SSOT for DGC evidence closure. A coded transition proves only that exact bound subjects passed the declared verifier under explicit theorem/engineering assumptions. It never substitutes for the external observation required by that stage.

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

The order is evidence, not presentation. Statistical method, CCF, G1–G5, fault semantics, external-verifier method surface and verifier trust policy must be frozen before outcome-bearing execution. B2 is calibration-only. Downstream evidence cannot redefine the method after seeing confirmatory outcomes.

## 2. `T_exec`: immutable execution source identity

Every scientific stage in one generation is bound to one clean Git commit/tree:

```text
T_exec = (repo_commit, repo_tree)
```

`_assert_repository_identity()` requires HEAD/tree to equal the ledger identity and requires a clean tracked worktree. Outcome-bearing execution is therefore not permitted while executable/statistical/scorer/policy/methodology source is moving.

## 3. Materialization and partition

`MATERIALIZED_VERIFIED` is recomputed from frozen external source authority and actual materialized bytes. A self-consistent receipt is insufficient.

Primary tasks are deterministically split before outcomes into pairwise-disjoint calibration, primary-confirmatory and G1 unseen-task populations. B2 may use only calibration examples and explicitly forbids both downstream populations.

## 4. Pre-outcome freeze

Before B2/confirmatory outcomes the generation freezes:

- execution manifests;
- model/prompt/tools/environment/container identities;
- budget and pricing snapshot;
- scorer and statistical plan;
- CCF semantics;
- G1–G5 registry and no-retuning rule;
- fault-injection matrix;
- P19 external-verifier method/runtime/test surface;
- P19 verifier trust policy.

The final B0/B1/B2/B3/DGC harness is frozen after fitted-B2 identity exists and before confirmatory execution.

## 5. Trial sizing versus final inference

Cluster-aware sizing and empirical-Bernstein width planning are **planning authorities only**. They may estimate required resources from calibration evidence; they cannot authorize P9.

Current final primary inference is V5.1:

1. exact frozen-panel fact; and
2. anytime-valid average-conditional-mean inference using Howard–Ramdas–McAuliffe–Sekhon Theorem 4 with exact polynomial-stitching Eq. (10).

The primary target is the precommitted bounded adapted-sequence average conditional mean, not an iid population mean. Provider-request independence is not a primary validity assumption. V5.1 freezes the exact binary64 `zeta(1.4)` reference value and boundary-parameter digest. Historical V4/V5 generations cannot authorize current promotion.

## 6. Confirmatory/P9 contract

`CONFIRMATORY_EXECUTED` requires the complete frozen `task × policy × replicate` population, replayable result/evidence bytes, coordinator audit chain and physical-cost subjects.

`P9_SUPPORTED` requires exact-panel cost/quality/regret conditions against B0–B3, V5.1 anytime lower-bound support, exact paired population coverage, ten-component physical-cost verification, frozen multiplicity allocation, CCF audit completeness and raw-subject/lineage replay.

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

`GENERALIZATION_SUPPORTED` means support on the five preregistered shifts only. It is not a universal-generalization claim. The final two-family product claim uses an explicit intersection–union AND composition.

## 8. Fault tolerance

`FAULT_TOLERANCE_SUPPORTED` is not a boolean chaos-test declaration. Each frozen fault class requires typed injection evidence, raw artifact binding, state-transition evidence and an evidence-bound audit event. Complete case coverage, no unauthorized promotion, no budget bypass and no duplicate side-effect commit are required.

## 9. Independent replication

Independent replication requires the same frozen methodology but fresh execution/result population, physical-cost population, CCF population, scientific P9 result and externally signed replication attestation.

Fresh subject identity and signature possession are machine-verifiable. Social independence is externally attested, never machine-proven:

```text
social_independence_machine_proven = false
```

## 10. Family P19 V3 portable replay root

Each canonical workload family receives its own `DGC_FAMILY_P19_EVIDENCE_ROOT_V3`. Required families are exactly:

```text
SWE_BENCH_VERIFIED
TERMINAL_BENCH_2_1
```

P19 V3 seals the pre-P19 ledger/receipt chain, stage evidence, methodology anchors, raw subject roots and an exact closed `external_replay_inputs` locator population. Each replay locator binds repository-relative path, SHA-256 and byte count. Missing, duplicate, escaping or byte-mismatched locators fail closed. A verifier must not discover an authority by scanning the repository for a matching digest.

## 11. External P19 semantic replay — Plan V4

Current implementation contract:

```text
DGC_P19_EXTERNAL_VERIFICATION_PLAN_V4
```

It defines exactly eight checks:

1. `REPOSITORY_IDENTITY`;
2. `THEOREM_AND_PLAN_IDENTITY`;
3. `SUBJECT_ROOT_REHASH`;
4. `P19_SEAL_REBUILD`;
5. `PRIMARY_P9_RAW_REPLAY`;
6. `GENERALIZATION_G1_G5_RAW_REPLAY`;
7. `FAULT_TOLERANCE_RAW_REPLAY`;
8. `INDEPENDENT_REPLICATION_RAW_REPLAY`.

`cwc/governance/p19_external_verification_contract.py` is the check→method SSOT. Plan V4 requires exact `CHECK_METHOD_IDS`; a self-consistent replacement label cannot pass.

The executable entrypoint is:

```text
scripts/dgc_external_p19_verifier.py
```

The scientific replay engine is:

```text
cwc/governance/p19_external_replay.py
```

Each outcome check delegates to the canonical authority builders/verifiers and requires recomputed authority digests to equal the digests sealed in P19. External replay therefore does not create a second statistical interpretation.

### Full transitive governance runtime closure

The verifier does not freeze only wrapper modules. `VERIFIER_RUNTIME_DEPENDENCIES` is the deterministic sorted set of all Python files under:

```text
cwc/governance/**/*.py
```

Any governance semantic change invalidates the verifier runtime digest and requires a new pre-outcome freeze/regression cycle. This intentionally prefers conservative invalidation over a transitive-import substitution surface.

The canonical regression test population is also content-addressed and method-map-bound.

### Raw verification transcript

Each of the eight checks binds canonical receipt, stdout bytes, stderr bytes and replay evidence bytes. Report/receipt/raw-subject semantics are replayed before SSH signature acceptance.

## 12. Plan V4 freeze and activation lifecycle

Development state and frozen-verifier state are distinct.

While verifier source/tests are still changing, **do not materialize the canonical Plan V4**. Instead run:

```text
python scripts/dgc_p19_external_verifier_freeze_readiness.py
```

`DGC_P19_EXTERNAL_VERIFIER_FREEZE_READINESS_V1` requires:

- exact eight-handler/method population;
- full governance runtime closure;
- canonical regression-test closure;
- all freeze subjects Git-tracked and clean;
- deterministic candidate inactive Plan V4 digest;
- no untracked canonical plan masquerading as frozen evidence.

Once the surface is stable and readiness passes, materialize exactly one immutable inactive Plan V4 with `dgc_freeze_p19_external_verification_plan.py` or the equivalent inactive materializer. The inactive plan cannot authorize activation or product qualification.

Activation is a separate authority. It requires:

1. canonical Git-bound regression receipt with exit code 0;
2. exact source commit/tree, runtime/test manifests and method-map digest;
3. two distinct external verifier principals;
4. two distinct signer key materials from the frozen trust policy;
5. valid SSH signatures over the exact regression-attestation protocol;
6. `DGC_P19_EXTERNAL_VERIFIER_ACTIVATION_AUTHORITY_V1` replay.

Therefore:

```text
handlers_implemented = true
≠ regression_executed
≠ activation_authorized
≠ product_qualified
```

The canonical V4 plan artifact is intentionally not frozen while this verifier surface is still changing. No synthetic signature or `CI failure/success` label can substitute for dual signed regression evidence.

## 13. Frozen external trust

`P19_VERIFIER_TRUST_POLICY_V2` is caller-independent at terminal promotion. It requires at least two distinct verifier principals and at least two distinct SSH key materials; one key aliased under two principal names cannot satisfy verifier separation.

The current canonical trust policy is not activated with real external verifier keys, so product qualification remains fail-closed.

## 14. Global V5 portable product authority

Current terminal product authority:

```text
DGC_GLOBAL_PRODUCT_QUALIFICATION_AUTHORITY_V5
```

Global V5 validates the complete two-family evidence chain and SSH signatures while separating portable cryptographic truth from environment-specific verification provenance. P19 digest, verifier principal, attestation/report/signature hashes, frozen allowed-signers hash, SSH namespace and `signature_verified=true` are portable authority inputs. Local `ssh-keygen` path/binary hash/stdout/stderr remain forensic execution provenance, not portable product-authority identity.

## 15. Pointer V3

Current terminal replay index:

```text
artifacts/dgc-product-v1/PRODUCT_QUALIFICATION_POINTER_V3.json
```

Pointer V3 rehashes ledger/Global-V5 bytes, resolves both P19/report/attestation/signature populations and frozen verifier policy, rebuilds Global V5 semantically, and requires the terminal `PRODUCT_QUALIFIED` ledger receipt to bind that exact Global V5 artifact.

Current canonical state:

```text
activation_authorized = false
product_qualified_claimed = false
```

## 16. `T_pkg`: post-outcome packaging identity

Scientific closure ends under `T_exec`. Evidence packaging happens later under descendant revision `T_pkg`.

```text
freeze method + inactive verifier plan + trust policy
→ externally validate/activate verifier before outcome-bearing execution
→ commit T_exec
→ execute/close scientific stages while scientific source remains T_exec
→ external P19 replay + signatures
→ Global V5
→ terminal scientific evidence
→ create T_pkg
→ add disclosed evidence + terminal pointer metadata
→ verify append-only delta
→ graph-complete bundle
→ deterministic double-build release
```

`DGC_EVIDENCE_PACKAGING_AUTHORITY_V2` rejects post-outcome source/methodology/verifier-plan mutation, deletion, mode changes, symlink/special Git objects and ambiguous paths.

## 17. Qualified evidence bundle V5

Current graph authority:

```text
DGC_QUALIFIED_EVIDENCE_BUNDLE_AUTHORITY_V5
```

It derives release subjects from the actual Pointer/P19/Global-V5 graph, including ledger, Global V5, source registry, trust policy/store, both P19 V3 roots, stage evidence, methodology anchors, raw subject roots, P19 external replay inputs, reports/attestations/signatures, frozen Plan V4, verifier entrypoint, full verifier runtime dependency closure and all check receipts/stdout/stderr/evidence.

Every required file must be either unchanged `EXECUTION_SOURCE_T0` or approved append-only `PACKAGING_EVIDENCE_T1`. Untracked evidence, omitted replay/transcript vertices, mutated verifier dependencies or post-hoc source changes fail closed.

## 18. Deterministic release

Qualified release keeps execution source and packaging evidence as separate archive roles, hashes every authority/manifest and performs a product-qualified double build requiring byte-identical outputs. No SLSA conformance level is claimed:

```text
slsa_conformance_claim = false
```

## 19. Verification execution state

The focused verifier/closure surface is wired into `.github/workflows/dgc-product-evidence.yml`, including Plan V4, regression/activation, freeze readiness, eight-check replay, P19 V3 and Bundle V5 falsifiers.

Recent GitHub Actions jobs repeatedly terminated before repository steps with:

```text
steps = null
logs_url = null
```

Classification until an exact current-head run actually executes:

```text
CI_EXECUTION_UNAVAILABLE
focused_pytest_execution = UNKNOWN
```

This is neither code PASS nor a demonstrated code regression.

## 20. Current truth

The external empirical campaign has not been completed. Real SWE/Terminal execution, physical provider-cost evidence, P9, G1–G5, fault campaign, independent replication, two real P19 roots, external P19 verifier regression signatures and P19 verification signatures remain empirical obligations.

Mandatory truth:

```text
PRODUCT_QUALIFIED = false
PRODUCTION_CONTROL_AUTHORIZED = false
external_verifier_plan_v4_activation_authorized = false
```

Current mathematical SSOT:

- `artifacts/dgc-product-v1/PREREGISTRATION.md`
- `docs/DGC_PRODUCT_STATISTICAL_PLAN_v5.md`
- `docs/DGC_STATISTICAL_AUTHORITY_v5.md`
- `docs/DGC_THEOREM_AUDIT_v5.md`

Operational evidence-closure SSOT:

- `docs/DGC_EVIDENCE_CLOSURE_EXECUTOR_v1.md`

Release provenance SSOT:

- `docs/DGC_RELEASE_PROVENANCE_v1.md`
