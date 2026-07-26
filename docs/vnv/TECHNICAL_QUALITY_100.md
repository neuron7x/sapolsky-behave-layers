# Technical Quality 100

This is the execution ledger for the 100-task mathematics, computer-science,
testing, code-quality, and system-design hardening programme. `DONE` means the
acceptance condition has executable evidence in the repository; `OPEN` is not a
claim of completion. IDs are stable and must not be renumbered.

| ID | State | Area | Acceptance condition |
|---|---|---|---|
| TQ-001 | DONE | Math input | Empty utility matrices fail closed |
| TQ-002 | DONE | Math input | Zero-action utility matrices fail closed |
| TQ-003 | DONE | Math input | Ragged utility matrices fail closed |
| TQ-004 | DONE | Math input | Non-finite utility cells fail closed |
| TQ-005 | DONE | Probability | Prior length must equal context count |
| TQ-006 | DONE | Probability | Negative prior mass fails closed |
| TQ-007 | DONE | Probability | Non-finite prior mass fails closed |
| TQ-008 | DONE | Probability | Prior normalization uses zero relative tolerance |
| TQ-009 | DONE | Certificate | Non-finite gap estimates fail closed |
| TQ-010 | DONE | Certificate | Non-finite standard errors fail closed |
| TQ-011 | DONE | Certificate | Context/action counts must be positive |
| TQ-012 | DONE | Certificate | Delta must be finite and strictly inside `(0,1)` |
| TQ-013 | DONE | Cost | Route cost must be finite and non-negative |
| TQ-014 | DONE | Complexity | Sample-complexity inputs share certificate validation |
| TQ-015 | DONE | Simulation | Noise generation validates matrix and scale |
| TQ-016 | DONE | Simulation | Calibration trial count must be positive |
| TQ-017 | DONE | Bootstrap | Bootstrap replication count must be at least two |
| TQ-018 | DONE | Bootstrap | Bootstrap scale must be finite and non-negative |
| TQ-019 | DONE | Bootstrap | Declared and observed matrix dimensions must match |
| TQ-020 | DONE | Metamorphic | Positive affine utility transformation law is tested |
| TQ-021 | OPEN | Proof | Migrate decisions from expectation-only to corrected bound |
| TQ-022 | OPEN | Proof | Deprecate ambiguous original lower-bound API explicitly |
| TQ-023 | OPEN | Proof | Encode theorem assumptions in a machine-readable contract |
| TQ-024 | DONE | Proof | Test corrected-bound monotonicity in delta |
| TQ-025 | DONE | Proof | Test corrected-bound monotonicity in standard error |
| TQ-026 | DONE | Proof | Test corrected-bound monotonicity in action count |
| TQ-027 | DONE | Proof | Test zero-noise exactness |
| TQ-028 | DONE | Proof | Test single-action oracle gap is exactly zero |
| TQ-029 | OPEN | Proof | Add numerical tolerance policy for certificate comparisons |
| TQ-030 | OPEN | Proof | Cross-check analytic bounds with high-precision arithmetic |
| TQ-031 | DONE | Statistics | Add Wilson upper confidence bound for simulated FPR |
| TQ-032 | DONE | Statistics | Replace empirical `FPR <= delta` point checks with CI checks |
| TQ-033 | OPEN | Statistics | Add deterministic sequential Monte Carlo stopping |
| TQ-034 | OPEN | Statistics | Add family-wise calibration across null configurations |
| TQ-035 | DONE | Statistics | Report Monte Carlo standard error in every simulation |
| TQ-036 | OPEN | Statistics | Add minimum detectable effect calculation |
| TQ-037 | DONE | Statistics | Separate estimation and validation RNG streams |
| TQ-038 | OPEN | Statistics | Add seed-sensitivity envelope |
| TQ-039 | OPEN | Statistics | Add heavy-tail robustness falsification |
| TQ-040 | OPEN | Statistics | Add heteroskedastic-noise falsification |
| TQ-041 | DONE | Metamorphic | Test action-permutation invariance |
| TQ-042 | DONE | Metamorphic | Test context-permutation invariance with matched priors |
| TQ-043 | DONE | Metamorphic | Test utility translation invariance |
| TQ-044 | DONE | Metamorphic | Test positive utility-scale equivariance |
| TQ-045 | DONE | Metamorphic | Test signal-permutation invariance |
| TQ-046 | DONE | Metamorphic | Test independent-signal refinement invariance |
| TQ-047 | DONE | Metamorphic | Test duplicate-action invariance |
| TQ-048 | DONE | Metamorphic | Test zero-probability context invariance |
| TQ-049 | OPEN | Metamorphic | Test hardlink/path-order corpus invariants |
| TQ-050 | OPEN | Metamorphic | Test checkpoint manifest order independence |
| TQ-051 | OPEN | Numerics | Bound mutual-information cancellation error |
| TQ-052 | DONE | Numerics | Add compensated summation to probability aggregates |
| TQ-053 | OPEN | Numerics | Define underflow policy for tiny joint masses |
| TQ-054 | OPEN | Numerics | Stress-test probabilities near machine epsilon |
| TQ-055 | OPEN | Numerics | Stress-test extreme finite utility ranges |
| TQ-056 | DONE | Numerics | Reject boolean values where integer counts are required |
| TQ-057 | OPEN | Numerics | Detect integer overflow in resource estimates |
| TQ-058 | OPEN | Numerics | Test exact duplicate-byte accounting at zero-byte files |
| TQ-059 | OPEN | Numerics | Verify SHA streaming across chunk boundaries |
| TQ-060 | OPEN | Numerics | Add cross-implementation digest oracle test |
| TQ-061 | OPEN | Types | Replace heterogeneous certificate dictionaries with TypedDict |
| TQ-062 | OPEN | Types | Introduce validated probability-vector value type |
| TQ-063 | OPEN | Types | Introduce validated finite-scalar constructors |
| TQ-064 | OPEN | Types | Make status values exhaustive literals |
| TQ-065 | OPEN | Types | Remove unchecked `Any` from readiness results |
| TQ-066 | OPEN | Types | Type artifact registry schema |
| TQ-067 | OPEN | Types | Type claim registry schema |
| TQ-068 | OPEN | Types | Type corpus audit records |
| TQ-069 | OPEN | Types | Add static exhaustiveness test for evidence categories |
| TQ-070 | OPEN | Types | Add pyright-compatible public interfaces |
| TQ-071 | OPEN | Architecture | Separate estimators, decisions, and simulation harnesses |
| TQ-072 | OPEN | Architecture | Centralize mathematical domain validation |
| TQ-073 | OPEN | Architecture | Add dependency-direction contract for experiment commons |
| TQ-074 | OPEN | Architecture | Add pure-core/no-I/O boundary test |
| TQ-075 | OPEN | Architecture | Version every machine-readable result schema |
| TQ-076 | OPEN | Architecture | Add backward-compatibility fixtures for schemas |
| TQ-077 | OPEN | Architecture | Define deterministic serialization contract |
| TQ-078 | OPEN | Architecture | Add atomic artifact-write utility |
| TQ-079 | OPEN | Architecture | Add interrupted-write recovery test |
| TQ-080 | OPEN | Architecture | Add resource budgets for every assurance gate |
| TQ-081 | OPEN | Security | Reject path traversal in artifact references |
| TQ-082 | OPEN | Security | Reject symlinked required artifacts |
| TQ-083 | OPEN | Security | Add decompression-bomb preflight policy |
| TQ-084 | OPEN | Security | Add archive member path sanitization |
| TQ-085 | OPEN | Security | Add Unicode path-confusable reporting |
| TQ-086 | OPEN | Security | Verify secret scanning covers full Git history |
| TQ-087 | OPEN | Security | Add malicious checkpoint regression corpus |
| TQ-088 | OPEN | Security | Add dependency-license policy gate |
| TQ-089 | OPEN | Security | Verify immutable container provenance |
| TQ-090 | OPEN | Security | Add least-privilege CI token audit |
| TQ-091 | DONE | CI | Enforce task-ledger schema and unique IDs |
| TQ-092 | DONE | CI | Require evidence for every `DONE` task |
| TQ-093 | OPEN | CI | Detect weakened thresholds in merge-request diffs |
| TQ-094 | OPEN | CI | Detect removed tests without explicit replacement evidence |
| TQ-095 | OPEN | CI | Split long experiment suite into deterministic shards |
| TQ-096 | OPEN | CI | Add per-shard timeout and runtime regression budget |
| TQ-097 | OPEN | CI | Merge shard reports into one signed assurance result |
| TQ-098 | OPEN | Docs | Link theorem assumptions to executable tests |
| TQ-099 | OPEN | Docs | Link every readiness blocker to a closure protocol |
| TQ-100 | OPEN | Release | Require exact-SHA post-merge verification attestation |

Current closure: **41/100 DONE**. The denominator is fixed. A task may move to
`DONE` only in the same change that adds its executable acceptance evidence.
