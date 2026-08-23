# DGC Evidence Closure Status v1

Date: 2026-08-23

This matrix separates **implementation/protocol closure** from **empirical product evidence**. A coded gate is not evidence that the gate has passed, upstream source verification is not local materialization or execution, and a distributed control primitive is not evidence of frontier-scale operation.

| Phase | Protocol / engineering state | Empirical evidence state | Canonical interpretation |
|---|---|---|---|
| P0 Product claim freeze | PARTIAL | N/A | claim, metrics and statistical plan frozen; executable B0-B3 panel and full external harness not yet frozen |
| P1 Executable control plane | IMPLEMENTED_NARROW_PLUS_DISTRIBUTED_CONTROL | INTERNAL_VERIFIED_TARGETED | deterministic/fail-closed governance exists; distributed eval leases/retries/idempotency/budget/full-coverage/audit-chain are implemented; no large-scale operational claim |
| P2 Physical total cost | IMPLEMENTED_SCHEMA | NOT_VERIFIED_EXTERNAL | full product cost boundary and component provenance contracts exist; no provider/client trial population |
| P3 Strong baselines | IMPLEMENTED_FREEZE_CONTRACT_PLUS_ORACLE | NOT_FROZEN | B0-B3 required; B2 calibration/fitted-model digest is absent; exact CCF audit oracle measures value regret and avoidable cost against the frozen option set but does not replace B0-B3 |
| P4 Synthetic VOC oracle | IMPLEMENTED | SUPPORTED_SYNTHETIC_NARROW | useful mechanism evidence only |
| P5 Decision-sensitive workload mechanisms | PARTIAL | MIXED | internal mechanism evidence exists; broad mechanism panel is not external product evidence |
| P6 External workloads | SOURCE_VERIFIED | NOT_MATERIALIZED_OR_EXECUTED | SWE-bench Verified revision/file SHA and Terminal-Bench signed Git object chain are independently source-verified; neither family is locally materialized or confirmatorily executed in this environment |
| P7 Identical evaluation harness | IMPLEMENTED_CONTRACT | NOT_FROZEN_EXTERNAL | harness equality is machine-enforced; actual materialized task/model/tool/env/scorer manifests remain incomplete |
| P8 Repeated stochastic trials | FROZEN_PLAN_PLUS_DISTRIBUTED_COORDINATION | NOT_EXECUTED | deterministic calibration/confirmatory split; power-based repeated-trial rule; min 5 / cap 50; work population can be distributed without weakening evidence identity |
| P9 Quality NI + cost superiority | IMPLEMENTED_INFERENCE_PLUS_CCF_AUDIT | NOT_EXECUTED_EXTERNAL | simultaneous paired multi-baseline cost/quality/catastrophic-regret gate exists; CCF provides exact same-option-set oracle headroom, but no external DGC result exists |
| P10 30% commercial target boundary | CLOSED | NOT_ACHIEVED_PRODUCT | 30% is not a universal theorem or current commercial claim |
| P11 CPS primary economics | IMPLEMENTED | NOT_MEASURED_EXTERNAL | cost per accepted successful outcome and paired net-saving semantics exist |
| P12 Generalization | IMPLEMENTED_GATE | NOT_EXECUTED | exact G1-G5 no-retuning policy gate exists |
| P13 Governance robustness | IMPLEMENTED_PLUS_DISTRIBUTED_FAULT_CONTROLS | SUPPORTED_NARROW_INTERNAL | fault injection plus stale-lease, retry, duplicate-result, partial-population and budget attacks are killed internally; external/production fault evidence pending |
| P14 Proof-carrying execution | IMPLEMENTED | INTERNAL_VERIFIED | execution/statistical certificates exist; production certificate population absent |
| P15 Shadow mode | IMPLEMENTED_GATE | NOT_EXECUTED | shadow evidence cannot contain DGC control authority |
| P16 Bounded canary | IMPLEMENTED_GATE | PROHIBITED_CURRENTLY | canary requires PRODUCT_QUALIFIED + shadow PASS + hard rollback limits |
| P17 Product economics | IMPLEMENTED_SCHEMA | NOT_CLIENT_VERIFIED | no real customer/client economics certificate |
| P18 Independent replication | IMPLEMENTED_PACKAGE_GATE | NOT_EXECUTED | self-replay cannot satisfy independent replication |
| P19 Evidence bundle | IMPLEMENTED_VERIFIER | INCOMPLETE_BY_DESIGN | partial truthful bundle exists; missing external raw results/materialized environment/model/replication and SHA-seal |
| P20 Product promotion | IMPLEMENTED_FAIL_CLOSED | PRODUCT_QUALIFIED_FALSE | machine stage cannot promote without the entire external evidence chain |

## Current hard facts

- `CLIENT_VERIFIED = false`.
- `PRODUCT_QUALIFIED = false`.
- `PRODUCTION_CONTROL_AUTHORIZED = false`.
- `LARGE_SCALE_OPERATIONAL_EVIDENCE = false`.
- external source authority is explicitly staged as `IDENTIFIED -> SOURCE_VERIFIED -> MATERIALIZED_VERIFIED -> EXECUTED`; stage skipping is rejected by code/tests.
- both frozen external benchmark identities currently reach only `SOURCE_VERIFIED`.
- distributed confirmatory execution now has a deterministic evidence-preserving coordinator, but it has not been exercised on a real multi-node/cloud worker population.
- `OPENAI_API_KEY` and `ANTHROPIC_API_KEY` were absent in the current execution environment; no live provider experiment was substituted with synthetic evidence.
- GitHub Actions execution authority remains unavailable when jobs terminate before repository steps; this is not counted as PASS.

## External workload identities

### SWE-bench Verified

- upstream code repository commit: `7a21e05772954cc81471ae19d56f436cecf43c54`;
- Hugging Face dataset revision: `03e151cf5560b1af6a4363c6a9d766deaaea6b56`;
- expected dataset rows: 500;
- frozen parquet SHA-256: `bb5b123d29ce70107cc0951cf444894241c570a11d76aec452332c65b01e06d8`;
- Xet object hash: `a56a1bd760f419b97a17386af035d814d92517fbed8822cba7ea2d22a349839b`;
- upstream revision/file metadata independently confirms the frozen SHA/Xet identity;
- authority stage: `SOURCE_VERIFIED`;
- local materialization: **false**;
- execution: **false**.

### Terminal-Bench 2.1

- upstream commit: `7131e4375048a0e408a8fb404b5f499d726b695b`;
- GitHub commit signature: verified valid;
- repository tree: `ddbd9031e59804a04e24019fc408d51b56a4e773`;
- task tree: `2f0f5fdc68f0befd9b4745386eb8698264b00d8a`;
- dataset manifest Git blob: `6e7e030fd37a7cefdbd597badcf8560c8748d995`;
- expected tasks: 89;
- manifest carries a SHA-256 digest for every task;
- authority stage: `SOURCE_VERIFIED`;
- local materialization: **false**;
- execution: **false**.

Machine registry: `artifacts/dgc-product-v1/external_source_authority.json`.
Gate: `scripts/dgc_product_external_source_gate.py`.

## Counterfactual compute frontier

`cwc/governance/counterfactual_frontier.py` supplies an exact finite multi-resource offline audit oracle over the frozen per-task option table. It measures:

- value regret relative to the exact option-set allocation optimum;
- minimum cost required to match or exceed the candidate policy value without worse declared latency/risk;
- avoidable cost under the same frozen option set.

This closes a benchmark-strength gap but creates no external product evidence by itself. CCF is reported in addition to B0-B3, never instead of them.

## Distributed evaluation control

`cwc/governance/distributed_eval_control.py` freezes work as `task × policy × replicate` and enforces:

- deterministic work identity and claim order;
- bounded leases and retry counts;
- worst-case cost reservation before dispatch;
- preregistration-time rejection of structurally underbudgeted experiments;
- stale/forged/expired lease rejection;
- idempotent identical result commit;
- quarantine on conflicting duplicate evidence;
- full preregistered coverage before completion certification;
- hash-chained audit transitions.

Targeted local authority: `8/8` tests PASS; adversarial gate: `4/4` attacks killed. This is **engineering evidence only**. It does not count as multi-node throughput, accelerator utilization, queueing, network partition recovery, cloud reliability, load/soak or production-scale evidence.

## Verification topology limitation

Earlier targeted mathematical and product clean-room checks retain their own local authority. The external-source state machine passed 7/7 local targeted tests; its two-family registry/gate recomputation passed locally with `SOURCE_VERIFIED=2`, `MATERIALIZED_VERIFIED=0`, `EXECUTED=0`. The CCF exact allocator passed 7/7 targeted tests including 100 seeded comparisons to exhaustive enumeration, and its greedy-allocation falsifier passed. The distributed evaluation coordinator passed 8/8 targeted tests and 4/4 adversarial attacks locally.

A new **full current-tree local regression is not claimed**: the sandbox cannot resolve `github.com` to clone/materialize the current branch, while GitHub Actions continues to terminate before repository steps. Therefore single-tree full regression remains `UNKNOWN` until one of those execution authorities is available.

## Definition of the remaining frontier

No additional internal theorem, unit test, UI feature or cognitive module can substitute for the remaining product evidence. The executable frontier is:

`materialize+seal both frozen workload families -> freeze scorer+environment+model+tool+budget manifests -> calibration-only B2 fit + trial-count freeze -> run distributed confirmatory paired population on both external families -> simultaneous P9 gate + CCF headroom audit -> G1-G5 no-retuning generalization -> independent replication -> SHA-sealed P19 bundle -> PRODUCT_QUALIFIED -> shadow -> bounded canary -> sustained operational monitoring`.

Until that chain is observed, reporting “100% validated product” is prohibited by the system itself.
