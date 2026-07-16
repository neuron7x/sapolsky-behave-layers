# COGNITIVE–SEMANTIC ARCHITECTURE AUDIT
Protocol: DCSA v2.0 (`DCSA_PROTOCOL_V2.md`). Supersedes `DCSA_AUDIT_0001.md`.
Audit date: 2026-07-16. All gates re-executed fresh at the audited commit —
no status below is inherited from prior sessions.

## 0. EXECUTIVE VERDICT
- Audit status: COMPLETED on available evidence (code level). All model-level
  stages (2–5) are NOT_TESTED by data sufficiency, not by omission.
- Maximum supported claim level: **L1 (EXECUTABLE CONTRACT)** for WP-1
  instrumentation. WP-0 baseline: L1 (code executes, upstream-pristine).
  WP-2…WP-7: **pre-L0** — only operational definitions and falsifiers exist
  (`CWC_SEMANTIC_CONTRACT.md`); no architecture spec for Π_θ, M_t, Φ.
- Strongest verified result: full gate battery at commit `cb0fa6a` —
  lint clean, mypy --strict clean (20 files), 207 passed / 2 skipped,
  99.46% branch coverage (floor 95%), mutation kill 12/12, determinism gate
  green, deliverable checksums 50/50.
- Critical blocker: **L2 (MEASUREMENT VALIDITY) is BLOCKED** — instrumentation
  overhead never quantified on a real training run
  (BLOCKED_BY_MEASUREMENT_OVERHEAD, 4 GiB GPU); `ENERGY_STATUS = NOT_MEASURED`
  (pynvml path exercised only with mocks; no physical telemetry run).
- Next falsifying experiment: WP-1 L2 qualification run (see §10).

## 1. SYSTEM AND EVIDENCE METADATA
- Target architecture: `nanochat-cwc-baseline` = unmodified dense GPT
  (karpathy/nanochat fork; local master == origin/master, verified pristine)
  + `cwc/instrumentation` package (15 modules: FLOPs, VRAM, energy, latency,
  routing counters, manifest/writer evidence pipeline).
- Commit/checkpoint: commit `cb0fa6ac051f482fc69b07361b168148dfef4a8d`,
  branch `wp1-instrumentation`, dirty=0 (a cosmetic tool-induced `uv.lock`
  drift was restored to the committed state before the audit run; `.coverage`
  run-artifact removed). **No model checkpoint exists.**
- Dataset: none present (no DATASET_SPEC).
- Hardware: NVIDIA RTX 3050 Laptop, 4096 MiB VRAM; Python 3.10.20 pinned
  `.venv` from committed `uv.lock`.
- Seeds: N/A at code level (deterministic gates); no training seeds exist.
- Available evidence: SYSTEM_SPEC (docs/), SOURCE_CODE (commit + lock + suite).
- Missing evidence: EXECUTION_TRACE, MODEL_ARTIFACTS, DATASET_SPEC, BASELINES
  (trained), EXPERIMENT_PROTOCOL (runs). DERIVABLE without them: static-graph
  facts only. NOT_DERIVABLE: geometry, invariance, grounding, causality,
  Pareto, energy.
- Reproducibility status: REPRODUCIBILITY_STATUS=CLEAN;
  ENVIRONMENT_MATCH=pinned (uv.lock committed); ARTIFACT_INTEGRITY=VERIFIED
  (sha256sum -c WP1_SHA256SUMS: 50/50 pass, method: GNU coreutils, exact,
  status VERIFIED); CLAIMABLE_RUN=yes for code-level gates only;
  BLOCKING_REASONS=no checkpoint, no traces, 4 GiB VRAM ceiling.

## 2. CLAIM–EVIDENCE MATRIX
| Claim | Required evidence | Available evidence | Status | Reason |
|---|---|---|---|---|
| WP-1 reference implementation works | executed test battery at HEAD | 207 passed / 2 skipped (FA3-conditional, documented), fresh run at `cb0fa6a` | VERIFIED | directly executed this audit |
| Mathematical cores guarded against defects | mutation probe execution | 12/12 curated mutants killed, fresh run | VERIFIED | scope limit: 12 curated mutants, NOT general correctness |
| Evidence pipeline deterministic | byte-identical repeat runs | determinism gate green (8 tests, fresh run) | VERIFIED | code level only |
| Routing decision channel is degenerate (H=0) | architecture inspection | static dense graph, single execution path | VERIFIED | structural derivation; normalized entropy H/log K NOT_APPLICABLE (K=1, log K=0) |
| Metrics fit for cross-run comparison (L2) | overhead + error quantification on real runs | none | BLOCKED | BLOCKED_BY_MEASUREMENT_OVERHEAD; 4 GiB GPU |
| Energy measurement works | physical NVML telemetry on a real run | mock-based unit tests only | NOT_TESTED | ENERGY_STATUS = NOT_MEASURED |
| H_CWC (joint control beats static/independent) | L3–L4 ablation ladder (§8 protocol) | none — mechanism absent | HYPOTHESIS | falsifiers preregistered in `CWC_SEMANTIC_CONTRACT.md` |
| Any capability term (router/memory/depth/plasticity/utility/Pareto) | per-term gate | none | NOT_TESTED | tier ABSENT for all six |
| Test coverage 99.46% ⇒ scientific validity | — | — | INVALID | coverage ≠ hypothesis correctness (protocol §2); coverage supports L1 only |

## 3. COMPUTATIONAL GRAPH AND ROUTING
- Active graph: static; every token executes the identical dense path (all
  blocks, all heads, all MLPs). V, E fixed at compile time; no conditional
  edges exist.
- Routing entropy: H = 0 bits/token (value 0, unit bits/token, exact,
  method: structural derivation — path distribution is a point mass,
  status VERIFIED). Normalized entropy: NOT_APPLICABLE (K=1).
- Utilization / Gini / dead-module / overload / dropped-token / padding /
  cross-seed stability: NOT_APPLICABLE — no routing subsystem exists;
  `routing.py` counters are instrumentation awaiting a subject.
- Collapse indicators: N/A now. Thresholds (τ_dead, τ_entropy, τ_imbalance)
  MUST be preregistered before WP-2 training, per protocol Stage 1.3.
- Controller FLOPs: 0 (no controller exists; value exact, status VERIFIED).
- Controller latency: 0 (same).
- Status: VERIFIED (structural facts only).

## 4. REPRESENTATION GEOMETRY
- Methods actually applicable: **none** — no activations, no checkpoint.
- Effective rank / CKA / RSA / local dimension: NOT_TESTED.
- Fisher approximation: NOT_TESTED (no gradients; when available, report
  approximation type per protocol Stage 2.3).
- RIEMANN_CURVATURE = INVALID_REQUEST (manifold assumption untested; no data).
- Unsupported geometric claims found in prior docs: none surviving —
  `DCSA_AUDIT_0001.md` already declined to fabricate these; v1's "grounding
  ratio UNDEFINED" is restated here as NOT_TESTED-with-missing-instrument.
- Status: NOT_TESTED (data sufficiency gate).

## 5. SEMANTIC INVARIANCE AND GROUNDING
- T_same: not constructed (requires oracle-verified paraphrase/refactor set).
- T_change: not constructed (requires negation/role-swap/intervention set
  with verified annotation).
- Invariance / Sensitivity / Action relevance / GCS: NOT_TESTED.
- Commutativity test: NOT_TESTED (no f, g, paired samples, or preregistered ε).
- Note: the falsifiers in `CWC_SEMANTIC_CONTRACT.md` §§1–2 map onto
  Sensitivity and Action-relevance arms; they become executable at WP-2+.
- Status: NOT_TESTED.

## 6. ADVERSARIAL AND CAUSAL FAILURES
- Perturbation set: not constructible — Δ_valid needs a model and an oracle.
- Oracle: absent.
- Worst-case / random-control degradation: NOT_TESTED.
- Failure coordinate: N/A.
- Alternative explanation ledger (code-level negatives that DID occur and were
  falsified-and-fixed during WP-1 hardening, recorded for provenance):
  (1) two weak tests exposed by mutation probe (percentile upper-index,
  bootstrap two-sided tail); (2) constant-input ULP loss in percentile across
  3 script copies; (3) stale-.pyc bytecode poisoning during mutation probing
  (mutate→restore within one mtime-second). All three are instrument-level,
  none is a model-level semantic failure.
- Status: NOT_TESTED (model level); VERIFIED (instrument-level negative log).

## 7. COMPUTE-EQUIVALENT BASELINES
| Model | Quality | FLOPs | VRAM | p95 latency | Energy | Transfer | Adaptation |
|---|---:|---:|---:|---:|---:|---:|---:|
| B0 dense static (nanochat) | NOT_TESTED | ledger-ready | NOT_TESTED | NOT_TESTED | NOT_MEASURED | — | — |
| B1 random router | DOES_NOT_EXIST | — | — | — | — | — | — |
| B2 frozen heuristic router | DOES_NOT_EXIST | — | — | — | — | — | — |
| B3 learned router | DOES_NOT_EXIST | — | — | — | — | — | — |
| B4 fixed-depth compute-matched | DOES_NOT_EXIST | — | — | — | — | — | — |
| B5 static MoE | DOES_NOT_EXIST | — | — | — | — | — | — |

- Compute parity: NOT_TESTABLE (nothing to pair). The parity *instrument*
  (FLOP ledger + manifest) is VERIFIED at L1 and is the only section of this
  stage already serviceable.
- Statistical method: preregistered by protocol (≥3/≥5 seeds, paired bootstrap
  95% CI); no runs exist.
- Confidence intervals: none (no data).
- Pareto verdict: **NOT_TESTED** (`TEST_PARETO_CLAIM` would return
  INSUFFICIENT_SEEDS/COMPUTE_MISMATCH degenerately; the honest verdict is that
  the claim is not yet evaluable).

## 8. FALSIFICATION OUTCOME
- Hypotheses rejected: none at model level (none were testable).
- Hypotheses surviving: none claimed.
- Untested hypotheses: H_CWC; all six capability terms; energy-measurement
  liveness; instrumentation-overhead acceptability.
- Confounds (watch list): Cyrillic-with-trailing-space repo path is a known
  phantom-failure class in this user's environment (manifested in another
  project); current suite is green under it, but any future unexplained
  loader/test failure must check path handling FIRST. Locale: `sha256sum -c`
  emits «Гаразд», not "OK" — grep-based CI checks must not match on "OK".
- Required negative controls (before any L3 claim): random router, frozen
  router, removed component, noop-instrumentation run — all preregistered in
  `CWC_SEMANTIC_CONTRACT.md` and protocol §8.

## 9. FINAL CLAIM BOUNDARY
### Supported
- "WP-1 instrumentation reference implementation works" (L1, VERIFIED).
- "The evidence pipeline is deterministic at code level" (VERIFIED).
- "The dense baseline has a zero-capacity routing channel" (VERIFIED, structural).
- "The measurement substrate is ready to *become* qualified" (L2 pending one
  experiment).

### Not supported
- Any efficiency, adaptivity, intelligence, or Pareto claim about CWC.
- Any statement that a learnable router / memory / dynamic depth / plasticity
  exists or contributes.
- Any energy figure (no physical telemetry has ever been recorded).

### Prohibited wording (until the corresponding gate is green)
- "CWC works / thinks / adapts"; "learnable router" in denoting mode;
  "compute-equivalent" (no parity pair exists); "Pareto advantage";
  "energy-efficient"; "metrics are production-qualified".

## 10. NEXT DECISIVE EXPERIMENT (WP-1 → L2)
- Intervention: train the smallest nanochat config that fits 4 GiB (or the
  largest CPU-feasible micro-config if none fits — then hardware becomes an
  explicit BLOCKED reason), in two arms: (A) full instrumentation ON,
  (B) noop adapter (`cwc/instrumentation/noop.py`) — identical manifests,
  identical seeds.
- Controls: (C) raw run with no instrumentation import at all (isolates
  import/patch cost); noop-vs-raw separates adapter overhead from measurement
  overhead.
- Budget: preregistered fixed token budget; ≥3 seeds per arm (exploration
  tier).
- Primary metrics: wall-clock overhead ratio A/C; step-time p50/p95; peak
  allocated VRAM delta; energy telemetry liveness (nonzero counters,
  nonfinite_input_count == 0).
- Failure criterion (preregistered NOW): overhead ratio > 1.05 ⇒
  "metrics fit for comparison" is REFUTED at this scale; dead energy counters
  ⇒ ENERGY_STATUS remains NOT_MEASURED and the energy module is demoted to
  NOT_TESTED in all reports.
- Success criterion: overhead ≤ 1.05 with paired bootstrap 95% CI across
  seeds excluding 1.05, and live energy telemetry ⇒ L2 unlocked; only then
  may WP-2 (learned routing) begin per protocol §8.
