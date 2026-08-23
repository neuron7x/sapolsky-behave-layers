# DGC Evidence Closure Status v1

Date: 2026-08-23

This matrix separates **implementation/protocol closure** from **empirical product evidence**. A coded gate is not evidence that the gate has passed; upstream source verification is not local materialization or execution; a distributed control primitive is not evidence of frontier-scale operation; an implemented learned baseline is not a fitted external baseline; and a deterministic release builder is not a product-qualified release.

| Phase | Protocol / engineering state | Empirical evidence state | Canonical interpretation |
|---|---|---|---|
| P0 Product claim freeze | PARTIAL | N/A | claim, primary metrics and statistical plan are frozen; complete external confirmatory generations are not yet frozen |
| P1 Executable control plane | IMPLEMENTED_NARROW_PLUS_DISTRIBUTED_CONTROL | INTERNAL_VERIFIED_TARGETED | deterministic/fail-closed governance plus evidence-preserving leases/retries/idempotency/budget/full-coverage/audit-chain are implemented; no large-scale operational claim |
| P2 Physical total cost | IMPLEMENTED_SCHEMA | NOT_VERIFIED_EXTERNAL | model/router/countermodel/retrieval/tools/verification/human/infra/retry/failure-loss boundary exists; no provider/client confirmatory population |
| P3 Strong baselines | B0_B3_CONTRACTS_PLUS_B2_IMPLEMENTATION_PLUS_CCF | NOT_FITTED_EXTERNAL | B2 learned cost-quality router is executable and calibration-only; external calibration/fitted-model digest is absent; exact CCF audit oracle measures value regret and avoidable cost but does not replace B0-B3 |
| P4 Synthetic VOC oracle | IMPLEMENTED | SUPPORTED_SYNTHETIC_NARROW | useful mechanism evidence only |
| P5 Decision-sensitive workload mechanisms | PARTIAL | MIXED | internal mechanism evidence exists; broad external mechanism evidence is absent |
| P6 External workloads | SOURCE_VERIFIED | NOT_MATERIALIZED_OR_EXECUTED | SWE-bench Verified and Terminal-Bench 2.1 source identities are independently frozen/verified; neither family is locally materialized or confirmatorily executed in this environment |
| P7 Identical evaluation harness | CONTENT_ADDRESSED_CONTRACT_PLUS_GENERATION_ROOT | NOT_FROZEN_EXTERNAL | harness fields require SHA-256 content identities; `ConfirmatoryGenerationRoot` cross-binds source/workload/harness/baselines/plan/policies/repo/distributed spec; no external root can be minted before materialization/B2 fit |
| P8 Repeated stochastic trials | FROZEN_CLUSTER_AWARE_PLAN_PLUS_DISTRIBUTED_COORDINATION | NOT_SIZED_OR_EXECUTED_EXTERNAL | V2 prevents pseudoreplication: between-task variance creates an irreducible task-level floor; calibration variance components and final repeat count remain external |
| P9 Quality NI + cost superiority | IMPLEMENTED_INFERENCE_PLUS_CCF_AUDIT | NOT_EXECUTED_EXTERNAL | simultaneous paired multi-baseline cost/quality/catastrophic-regret gate exists; CCF supplies exact same-option-set oracle headroom; no external result exists |
| P10 30% commercial target boundary | CLOSED | NOT_ACHIEVED_PRODUCT | 30% remains a commercial target, not a theorem or current claim |
| P11 CPS primary economics | IMPLEMENTED | NOT_MEASURED_EXTERNAL | cost per accepted successful outcome and paired net-saving semantics exist |
| P12 Generalization | IMPLEMENTED_GATE | NOT_EXECUTED | G1-G5 no-retuning policy gate exists; no external shift population has passed it |
| P13 Governance robustness | DISTRIBUTED_FAULTS_PLUS_COMBINATORIAL_PLUS_CONTINUOUS_ASSURANCE | SUPPORTED_NARROW_INTERNAL | targeted fault controls, exact finite schedule modelcheck, t-way coverage measurement and CONTINUE/HOLD/ROLLBACK assurance are implemented; production fault evidence absent |
| P14 Proof-carrying / formal assurance | CERTIFICATES_PLUS_SMT_CORE_PRESENT | FORMAL_EXECUTION_UNKNOWN | execution/statistical certificates exist; narrow SMT core is present, but local Z3 execution authority is unavailable and independent formal review is absent |
| P15 Shadow mode | IMPLEMENTED_GATE | NOT_EXECUTED | shadow evidence cannot contain DGC production control authority |
| P16 Bounded canary | IMPLEMENTED_GATE | PROHIBITED_CURRENTLY | canary requires PRODUCT_QUALIFIED + shadow PASS + hard rollback limits |
| P17 Product economics | IMPLEMENTED_SCHEMA | NOT_CLIENT_VERIFIED | no real customer/client economics certificate |
| P18 Independent replication | IMPLEMENTED_PACKAGE_GATE | NOT_EXECUTED | self-replay cannot satisfy independence |
| P19 Evidence/release bundle | VERIFIER_PLUS_DETERMINISTIC_DGC_RELEASE_BUILDER | INCOMPLETE_BY_DESIGN | exact tracked-population release builder and double-build gate exist; external results/replication are missing; historical root `RELEASE_MANIFEST.json` is not DGC authority |
| P20 Product promotion | IMPLEMENTED_FAIL_CLOSED | PRODUCT_QUALIFIED_FALSE | machine stage cannot promote without the entire external evidence chain |

## Current hard facts

- `CLIENT_VERIFIED = false`.
- `PRODUCT_QUALIFIED = false`.
- `PRODUCTION_CONTROL_AUTHORIZED = false`.
- `LARGE_SCALE_OPERATIONAL_EVIDENCE = false`.
- external source authority is staged as `IDENTIFIED -> SOURCE_VERIFIED -> MATERIALIZED_VERIFIED -> EXECUTED`; stage skipping is rejected.
- both frozen external benchmark identities currently reach only `SOURCE_VERIFIED`.
- B2 learned routing is implemented, but no external calibration fit has been minted.
- cluster-aware statistical-plan V2 is frozen pre-execution, but external between/within-task variance components have not been estimated.
- confirmatory generation-root logic is implemented, but no external generation root can be validly minted before materialization, B2 fit and final trial sizing.
- distributed confirmatory execution has an evidence-preserving coordinator and exact finite timing modelcheck, but it has not operated on a real multi-node/cloud worker population.
- continuous assurance and combinatorial coverage are engineering controls, not production evidence.
- the formal SMT core is present; `FORMAL_CORE_EXECUTION` remains `UNKNOWN` where Z3 cannot run.
- the DGC-specific deterministic release builder is implemented; the repository-root historical `RELEASE_MANIFEST.json` must not be represented as current DGC release authority.
- no live provider experiment has been substituted with synthetic evidence.
- GitHub Actions runs that terminate before repository steps are `CI_EXECUTION_UNAVAILABLE`, not PASS or code FAIL.

## External workload identities

### SWE-bench Verified

- upstream code repository commit: `7a21e05772954cc81471ae19d56f436cecf43c54`;
- Hugging Face dataset revision: `03e151cf5560b1af6a4363c6a9d766deaaea6b56`;
- expected dataset rows: 500;
- frozen parquet SHA-256: `bb5b123d29ce70107cc0951cf444894241c570a11d76aec452332c65b01e06d8`;
- Xet object hash: `a56a1bd760f419b97a17386af035d814d92517fbed8822cba7ea2d22a349839b`;
- authority stage: `SOURCE_VERIFIED`;
- local materialization: **false**;
- execution: **false**.

### Terminal-Bench 2.1

- upstream commit: `7131e4375048a0e408a8fb404b5f499d726b695b`;
- GitHub commit signature: verified valid;
- repository tree: `ddbd9031e59804a04e24019fc408d51b56a4e773`;
- task tree: `2f0f5fdc68f0befd9b4745386eb8698264b00d8a`;
- dataset manifest Git blob: `6e7e030fd37a7cefdbd597badcf8560c8748d995`;
- expected tasks: 89 with upstream per-task SHA-256 digests;
- authority stage: `SOURCE_VERIFIED`;
- local materialization: **false**;
- execution: **false**.

Machine registry: `artifacts/dgc-product-v1/external_source_authority.json`.
Gate: `scripts/dgc_product_external_source_gate.py`.

## B2 learned baseline

`cwc/governance/learned_baseline.py` implements a deliberately transparent strong baseline:

- frozen feature schema and action set;
- per-action ridge utility models;
- complete calibration-only counterfactual task/action table;
- confirmatory-task leakage rejection;
- deterministic lexicographic tie-breaking;
- calibration-task and fitted-model digests;
- explicit binding back into `BaselinePanelSeal`.

This closes the **algorithmic baseline gap**, not the external-fit gap. `baselines_frozen=false` remains correct until B2 is fitted on the frozen calibration partition and bound into B0-B3.

## Cluster-aware repeated-trial plan V2

Product qualification no longer treats repeated stochastic runs within one task as independent task draws.

The frozen sizing model is:

`Var(mean) = sigma_between^2 / N_tasks + sigma_within^2 / (N_tasks * R)`.

If the between-task term alone exceeds the target standard-error budget, the run terminates `UNDERPOWERED_TASK_HETEROGENEITY`; arbitrary repetitions cannot manufacture power. Variance components must come from calibration-only data.

## Counterfactual compute frontier

`cwc/governance/counterfactual_frontier.py` supplies an exact finite multi-resource offline audit oracle over the frozen per-task option table. It measures value regret, minimum cost required to match/exceed candidate value without worse declared latency/risk, and avoidable cost under the same option set. CCF is reported in addition to B0-B3, never instead of them.

## Distributed evaluation control

`cwc/governance/distributed_eval_control.py` freezes work as `task × policy × replicate` and enforces deterministic work identity/order, bounded leases/retries, cost reservation, underbudget rejection, stale/forged/expired lease rejection, idempotent identical commits, quarantine on conflicting duplicate evidence, full preregistered coverage, and a hash-chained audit trail.

Targeted local authority already recorded: `8/8` tests PASS; adversarial gate `4/4` killed. `scripts/dgc_distributed_eval_modelcheck.py` additionally enumerates the declared finite timing/worker schedule family. This is **engineering evidence only**, not a scale claim.

## Confirmatory generation root

`cwc/governance/confirmatory_generation.py` closes the cross-layer drift gap. Before outcome execution, one SHA-bound root must simultaneously agree on:

- materialized source authority and task/tree digests;
- exact repo commit/tree;
- executable-frozen B0-B3 panel;
- cluster-aware trial sizing;
- common controlled-comparison frame;
- per-policy governance/full-harness digests;
- distributed task/policy/repeat population;
- statistical plan.

Completion is accepted only for the same distributed spec and the full frozen population. Targeted local logic: `8/8 PASS`; canonical adversarial gate: `scripts/dgc_confirmatory_generation_attack.py`.

## Continuous and combinatorial assurance

`continuous_assurance.py` separates functionality, operations, human factors, security, compliance and large-scale-impact evidence and supports `CONTINUE / HOLD / ROLLBACK` authority transitions. `combinatorial_coverage.py` measures exact t-way interaction coverage rather than equating ordinary code coverage with behavior-space assurance.

These controls prepare future shadow/canary monitoring; neither is counted as current production qualification.

## Formal-core boundary

A narrow SMT safety core exists for selected budget/admission/Pareto obligations. It is not a proof of DGC as a whole. Where the pinned solver is unavailable, the only correct state is `FORMAL_CORE_EXECUTION=UNKNOWN`. Independent theorem review remains zero in the current proof ledger.

## Release assurance

`scripts/make_dgc_release.py` and `scripts/dgc_release_repro_gate.py` implement a DGC-specific deterministic release path over the exact tracked source/evidence population with normalized archive metadata and double-build comparison. Product-qualified release remains blocked by P20 and the incomplete external evidence bundle.

## Verification topology limitation

Targeted local component checks retain their scoped authority. The current remote head still lacks a successful repository-step GitHub Actions run; current jobs terminate with `steps=null`/no logs. Therefore a full single-tree regression of the latest remote head is not claimed.

The base project snapshot available in the execution runtime has been independently verified to match the PR base Git tree `d72c2e6ce7113236475dc699ee47207cc3b5504f`; transport of the complete current PR patch into that runtime remains the missing step for exact current-tree local reconstruction.

## Definition of the remaining frontier

No additional internal theorem, unit test, UI feature or cognitive module can substitute for the remaining product evidence. The executable frontier is:

`materialize+seal both frozen workloads -> freeze scorer/environment/model/tool/budget/pricing manifests -> calibration-only B2 fit -> estimate calibration-only between/within-task variance -> freeze repeat count -> mint one confirmatory generation root per family -> execute full distributed paired populations -> simultaneous P9 gate + CCF audit -> G1-G5 no-retuning generalization -> independent replication/formal review -> SHA-sealed P19 bundle -> PRODUCT_QUALIFIED -> shadow -> bounded canary -> sustained operational monitoring`.

Until that chain is observed, reporting “100% validated product” is prohibited by the system itself.
