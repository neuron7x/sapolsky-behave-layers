# DGC Evidence Closure Status v1

Date: 2026-08-22

This matrix separates **implementation/protocol closure** from **empirical product evidence**. A coded gate is not evidence that the gate has passed.

| Phase | Protocol / engineering state | Empirical evidence state | Canonical interpretation |
|---|---|---|---|
| P0 Product claim freeze | PARTIAL | N/A | claim, metrics and statistical plan frozen; executable B0-B3 panel and full external harness not yet frozen |
| P1 Executable control plane | IMPLEMENTED_NARROW | INTERNAL_VERIFIED | deterministic/fail-closed governance components exist; not production-qualified |
| P2 Physical total cost | IMPLEMENTED_SCHEMA | NOT_VERIFIED_EXTERNAL | full product cost boundary and component provenance contracts exist; no provider/client trial population |
| P3 Strong baselines | IMPLEMENTED_FREEZE_CONTRACT | NOT_FROZEN | B0-B3 required; B2 training algorithm can be frozen, but calibration/fitted-model digest is absent |
| P4 Synthetic VOC oracle | IMPLEMENTED | SUPPORTED_SYNTHETIC_NARROW | useful mechanism evidence only |
| P5 Decision-sensitive workload mechanisms | PARTIAL | MIXED | internal mechanism evidence exists; broad mechanism panel is not external product evidence |
| P6 External workloads | SOURCE_FROZEN | NOT_EXECUTED | SWE-bench Verified + Terminal-Bench 2.1 identities frozen; no confirmatory DGC execution |
| P7 Identical evaluation harness | IMPLEMENTED_CONTRACT | NOT_FROZEN_EXTERNAL | harness equality is machine-enforced; actual model/tool/env/scorer manifests incomplete |
| P8 Repeated stochastic trials | FROZEN_PLAN | NOT_EXECUTED | deterministic calibration/confirmatory split; power-based repeated-trial rule; min 5 / cap 50 for generation v1 |
| P9 Quality NI + cost superiority | IMPLEMENTED_INFERENCE | NOT_EXECUTED_EXTERNAL | simultaneous paired multi-baseline cost/quality/catastrophic-regret gate exists |
| P10 30% commercial target boundary | CLOSED | NOT_ACHIEVED_PRODUCT | 30% is not a universal theorem or current commercial claim |
| P11 CPS primary economics | IMPLEMENTED | NOT_MEASURED_EXTERNAL | cost per accepted successful outcome and paired net-saving semantics exist |
| P12 Generalization | IMPLEMENTED_GATE | NOT_EXECUTED | exact G1-G5 no-retuning policy gate exists |
| P13 Governance robustness | IMPLEMENTED | SUPPORTED_NARROW_INTERNAL | strong internal fault injection exists; external workload/production fault evidence pending |
| P14 Proof-carrying execution | IMPLEMENTED | INTERNAL_VERIFIED | execution/statistical certificates exist; production certificate population absent |
| P15 Shadow mode | IMPLEMENTED_GATE | NOT_EXECUTED | shadow evidence cannot contain DGC control authority |
| P16 Bounded canary | IMPLEMENTED_GATE | PROHIBITED_CURRENTLY | canary requires PRODUCT_QUALIFIED + shadow PASS + hard rollback limits |
| P17 Product economics | IMPLEMENTED_SCHEMA | NOT_CLIENT_VERIFIED | no real customer/client economics certificate |
| P18 Independent replication | IMPLEMENTED_PACKAGE_GATE | NOT_EXECUTED | self-replay cannot satisfy independent replication |
| P19 Evidence bundle | IMPLEMENTED_VERIFIER | INCOMPLETE_BY_DESIGN | partial truthful bundle exists; missing external raw results/environment/model/replication and SHA-seal |
| P20 Product promotion | IMPLEMENTED_FAIL_CLOSED | PRODUCT_QUALIFIED_FALSE | machine stage cannot promote without the entire external evidence chain |

## Current hard facts

- `CLIENT_VERIFIED = false`.
- `PRODUCT_QUALIFIED = false`.
- `PRODUCTION_CONTROL_AUTHORIZED = false`.
- live OpenAI/Anthropic execution in the current environment is blocked because provider credentials are absent.
- GitHub Actions execution authority remains unavailable when jobs terminate before repository steps; this is not counted as PASS.

## External workload identities

### SWE-bench Verified

- upstream code repository commit: `7a21e05772954cc81471ae19d56f436cecf43c54`;
- Hugging Face dataset revision: `03e151cf5560b1af6a4363c6a9d766deaaea6b56`;
- dataset rows: 500;
- frozen parquet SHA-256: `bb5b123d29ce70107cc0951cf444894241c570a11d76aec452332c65b01e06d8`.

### Terminal-Bench 2.1

- upstream commit: `7131e4375048a0e408a8fb404b5f499d726b695b`;
- repository tree: `ddbd9031e59804a04e24019fc408d51b56a4e773`;
- task tree: `2f0f5fdc68f0befd9b4745386eb8698264b00d8a`;
- dataset manifest Git blob: `6e7e030fd37a7cefdbd597badcf8560c8748d995`;
- expected tasks: 89;
- manifest carries a SHA-256 digest for every task.

## Definition of the remaining frontier

No additional internal theorem, unit test, UI feature or cognitive module can substitute for the remaining product evidence. The executable frontier is:

`materialize/freeze scorer+environment+model+tool+budget manifests -> calibration-only B2 fit + trial-count freeze -> confirmatory paired runs on both external families -> simultaneous P9 gate -> G1-G5 no-retuning generalization -> independent replication -> SHA-sealed P19 bundle -> PRODUCT_QUALIFIED -> shadow -> bounded canary`.

Until that chain is observed, reporting “100% validated product” is prohibited by the system itself.
