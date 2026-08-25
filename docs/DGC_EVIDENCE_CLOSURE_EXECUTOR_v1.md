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

`MATERIALIZED_VERIFIED` is recomputed from frozen external source authority and actual materialized bytes. A self-consistent receipt is insufficient. Primary tasks are deterministically split before outcomes into pairwise-disjoint calibration, primary-confirmatory and G1 unseen-task populations. B2 may use only calibration examples and explicitly forbids both downstream populations.

## 4. Pre-outcome freeze

Before B2/confirmatory outcomes the generation freezes execution manifests, model/prompt/tools/environment/container identities, budget/pricing, scorer/statistical plan, CCF, G1–G5/no-retuning semantics, fault matrix, P19 external-verifier method/runtime/test surface and verifier trust policy. The final B0/B1/B2/B3/DGC harness is frozen after fitted-B2 identity exists and before confirmatory execution.

## 5. Trial sizing versus final inference

Cluster-aware sizing and empirical-Bernstein width planning are planning authorities only. Current final primary inference is V5.1: exact frozen-panel fact plus anytime-valid average-conditional-mean inference using Howard–Ramdas–McAuliffe–Sekhon Theorem 4 with exact polynomial-stitching Eq. (10). The target is the precommitted bounded adapted-sequence average conditional mean, not an iid population mean. Provider-request independence is not a primary validity assumption. V5.1 freezes the exact binary64 `zeta(1.4)` reference and boundary-parameter digest.

## 6. Confirmatory/P9 contract

`P9_SUPPORTED` requires exact-panel cost/quality/regret conditions against B0–B3, V5.1 anytime support, exact paired coverage, ten-component physical-cost verification, frozen multiplicity, complete CCF audit and raw-subject/lineage replay. A favorable point estimate cannot rescue a failed confidence gate, and the confidence procedure cannot rescue an unfavorable exact panel.

Primary multiplicity:

```text
2 workload families × 4 baselines × 3 endpoints = 24 claims
```

## 7. G1–G5

Each G-axis requires exact shift-panel evidence plus V5.1 anytime support, exact source/model/pricing/perturbation identity, five policy arms, physical-cost evidence and no retuning.

```text
5 axes × 4 baselines × 3 endpoints = 60 claims per family
family FWER = 0.05
```

`GENERALIZATION_SUPPORTED` is limited to the five preregistered shifts. The final two-family product claim is an explicit intersection–union AND composition.

## 8. Fault tolerance

`FAULT_TOLERANCE_SUPPORTED` requires typed injection evidence, raw artifact binding, state-transition evidence, an evidence-bound audit event, complete case coverage, no unauthorized promotion, no budget bypass and no duplicate side-effect commit.

## 9. Independent replication

Independent replication requires the same methodology but fresh execution/result, physical-cost and CCF populations, a fresh scientific P9 result and an externally signed replication attestation. Social independence is externally attested, never machine-proven:

```text
social_independence_machine_proven = false
```

## 10. Family P19 V3 portable replay root

Each canonical family receives `DGC_FAMILY_P19_EVIDENCE_ROOT_V3`; required families are exactly `SWE_BENCH_VERIFIED` and `TERMINAL_BENCH_2_1`. P19 V3 seals the pre-P19 ledger/receipt chain, stage evidence, methodology anchors, raw subject roots and an exact closed `external_replay_inputs` population. Each locator binds repository-relative path, SHA-256 and byte count. Missing, duplicate, escaping or byte-mismatched locators fail closed; repository scanning by digest is not a valid replay method.

## 11. External P19 semantic replay — Plan V4

Current contract:

```text
DGC_P19_EXTERNAL_VERIFICATION_PLAN_V4
```

The exact eight checks are:

1. `REPOSITORY_IDENTITY`
2. `THEOREM_AND_PLAN_IDENTITY`
3. `SUBJECT_ROOT_REHASH`
4. `P19_SEAL_REBUILD`
5. `PRIMARY_P9_RAW_REPLAY`
6. `GENERALIZATION_G1_G5_RAW_REPLAY`
7. `FAULT_TOLERANCE_RAW_REPLAY`
8. `INDEPENDENT_REPLICATION_RAW_REPLAY`

`cwc/governance/p19_external_verification_contract.py` is the check→method SSOT. `scripts/dgc_external_p19_verifier.py` is the entrypoint and `cwc/governance/p19_external_replay.py` is the replay engine. Outcome checks delegate to canonical authority builders/verifiers and require recomputed digests to equal P19-sealed digests.

### Full transitive governance runtime closure

`VERIFIER_RUNTIME_DEPENDENCIES` is the deterministic sorted set of every Python module under:

```text
cwc/governance/**/*.py
```

This is intentionally conservative. Any governance semantic change invalidates the runtime digest and requires a new pre-outcome verifier freeze/regression cycle; wrapper-only hashing is insufficient.

Each external check additionally binds canonical receipt, stdout, stderr and evidence bytes. Report/receipt/raw-subject semantics are replayed before SSH signature acceptance.

## 12. Plan V4 freeze and activation lifecycle

While verifier source/tests are changing, the canonical Plan V4 must not be frozen. `DGC_P19_EXTERNAL_VERIFIER_FREEZE_READINESS_V1` computes the candidate inactive plan and requires exact handlers/methods, the full governance runtime closure, exact regression-test closure and Git-tracked/clean freeze subjects. An untracked canonical plan cannot masquerade as frozen evidence.

Readiness command:

```text
python scripts/dgc_p19_external_verifier_freeze_readiness.py
```

Once stable, an immutable **inactive** Plan V4 may be materialized. Activation is separate and requires a canonical Git-bound regression receipt plus two independent external signatures under the frozen trust policy and successful replay of `DGC_P19_EXTERNAL_VERIFIER_ACTIVATION_AUTHORITY_V1`.

Therefore:

```text
handlers_implemented = true
≠ regression_executed
≠ activation_authorized
≠ product_qualified
```

The canonical V4 plan is intentionally not frozen while this verifier surface is still changing.

## 13. Frozen external trust

`P19_VERIFIER_TRUST_POLICY_V2` is caller-independent and requires at least two distinct verifier principals and two distinct SSH key materials. One key aliased under two principal names cannot satisfy separation. Real external verifier keys/signatures are still absent.

## 14. Global V5 portable product authority

Current terminal product authority is `DGC_GLOBAL_PRODUCT_QUALIFICATION_AUTHORITY_V5`. It validates the two-family evidence chain and SSH signatures while separating portable cryptographic identity from machine-local signature-tool execution provenance.

## 15. Pointer V3

Current terminal replay index is `artifacts/dgc-product-v1/PRODUCT_QUALIFICATION_POINTER_V3.json`. Pointer V3 rehashes ledger/Global-V5 bytes, resolves both family P19/report/attestation/signature populations and frozen verifier policy, rebuilds Global V5 semantically, and requires the terminal ledger receipt to bind that exact authority.

Current canonical state:

```text
activation_authorized = false
product_qualified_claimed = false
```

## 16. `T_exec` versus `T_pkg`

Scientific execution and post-outcome packaging are distinct immutable subjects. `DGC_EVIDENCE_PACKAGING_AUTHORITY_V2` requires `T_exec` to be an ancestor of `T_pkg` and rejects post-outcome source/methodology/verifier-plan mutation, deletion, type/mode change, symlink/special Git objects and ambiguous paths.

## 17. Qualified evidence bundle V7

Current graph authority:

```text
DGC_QUALIFIED_EVIDENCE_BUNDLE_AUTHORITY_V7
```

It derives required release subjects from the actual Pointer/P19/Global-V5 graph. Required vertices include ledger, Global V5, source registry, verifier trust policy/store, both P19 V3 roots, stage evidence, methodology anchors, raw subject roots, portable P19 replay inputs, reports/attestations/signatures, active Plan V4, verifier entrypoint, full verifier dependency closure, dual-signed activation authority, canonical regression receipt/runtime/test manifests/stdout/stderr and every external-check receipt/stdout/stderr/evidence artifact.

Explicit invariants include:

```text
raw_p19_verification_transcripts_included = true
frozen_verification_plan_and_entrypoint_included = true
frozen_verifier_dependency_closure_included = true
dual_signed_verifier_activation_authority_included = true
activation_regression_evidence_included = true
portable_p19_replay_inputs_included = true
portable_global_v5_authority_included = true
all_required_subjects_git_bound = true
evidence_graph_complete = true
```

Every required file must be unchanged `EXECUTION_SOURCE_T0` or approved append-only `PACKAGING_EVIDENCE_T1`.

## 18. Deterministic release V7

Current release manifest schema:

```text
DGC_DETERMINISTIC_RESEARCH_RELEASE_V7
```

Qualified release emits separate deterministic execution-source and packaging-evidence archives, packaging authority, Bundle V7 authority, release manifest and `SHA256SUMS`. Product-tag release performs the full product-qualified build twice and requires byte-identical outputs. No SLSA conformance level is claimed.

## 19. Verification execution state

The focused verifier/closure surface is wired into `.github/workflows/dgc-product-evidence.yml`, including Plan V4, regression/activation, freeze readiness, eight-check replay, P19 V3 and Bundle V7 falsifiers. The workflow also fingerprints the full governance Python runtime surface before attempting canonical regression receipt generation.

Recent GitHub Actions jobs repeatedly terminated before repository steps with:

```text
steps = null
logs_url = null
```

Until a current-head run actually executes:

```text
CI_EXECUTION_UNAVAILABLE
focused_pytest_execution = UNKNOWN
canonical_verifier_regression_execution = UNKNOWN
```

This is neither code PASS nor a demonstrated code regression.

## 20. Current truth

The real empirical campaign is not complete. SWE/Terminal execution, physical provider-cost evidence, P9, G1–G5, fault campaign, independent replication, two real P19 roots, external verifier regression signatures and external P19 verification signatures remain obligations.

```text
PRODUCT_QUALIFIED = false
PRODUCTION_CONTROL_AUTHORIZED = false
external_verifier_plan_v4_activation_authorized = false
```

Mathematical SSOT:
- `artifacts/dgc-product-v1/PREREGISTRATION.md`
- `docs/DGC_PRODUCT_STATISTICAL_PLAN_v5.md`
- `docs/DGC_STATISTICAL_AUTHORITY_v5.md`
- `docs/DGC_THEOREM_AUDIT_v5.md`

Operational SSOT:
- `docs/DGC_EVIDENCE_CLOSURE_EXECUTOR_v1.md`

Release provenance SSOT:
- `docs/DGC_RELEASE_PROVENANCE_v1.md`
