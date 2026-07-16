# CWC EXECUTION REPORT
Protocol: CWC Claude Fable Execution Act v1.0.0. Executed 2026-07-16 by the
local agent. All phases A→I completed; the central causal question is answered
with an honest negative.

## 1. REPOSITORY STATE
- Canonical repository: `.../sapolsky-behave-layers/nanochat-cwc-baseline`
- Baseline commit: `92d63d4e8bb4df75c3b71618f31ddde2378b2bcd` (== Act baseline; PASS)
- Working branch: `wp1-instrumentation`
- Dirty state: clean at each commit (artifacts tracked; `.coverage` transient removed)
- Environment: Python 3.10.20, torch 2.9.1+cu128, RTX 3050 Laptop 4 GiB, pinned uv.lock

## 2. PHASE VERDICTS
| Phase | Status | Evidence | Blocker |
|---|---|---|---|
| A reconstruct evidence chain | PASS | `../wp1-release/` (Gate A, checksums valid) | — |
| B qualify instrumentation | PASS_WITH_ENERGY_EXCLUDED | overhead confirmatory, energy probe | energy INSTRUMENT_INVALID |
| C freeze experiment protocol | PASS | `preregistration/` committed pre-code | — |
| D minimal learned routing | PASS | RoutedTransformer + ADR-0002, 10/10 tests | — |
| E compute-equivalent controls | PASS | 5 configs, parity 0.03% | — |
| F multi-seed run | PASS (pilot) | `raw_runs/` 15 runs (5×3) | 3 seeds (≥5 for claim) |
| G statistical Pareto verdict | PASS | `statistics/analysis.json` | — |
| H publish evidence bundle | PASS | this bundle, `SHA256SUMS` 33 files | — |

## 3. WP-1 METROLOGY
- E2E overhead: median −0.46%, gate ≤1.0% → PASS
- GPU overhead: −0.21%, gate ≤1.0% → PASS
- 95% CI (paired): [+0.086%, +0.306%], gate upper ≤2.0% → PASS
- Energy status: UNAVAILABLE (INSTRUMENT_INVALID; NVML counter ~2× over-read)
- Claimable metrics: FLOPs, VRAM, latency, quality. NOT energy.

## 4. WP-2 IMPLEMENTATION
- Controller: straight-through top-K over per-block scores (ADR-0002)
- Hard budget: exactly K=4 of L=8 blocks/sequence, 0 violations
- Controls: dense, random, frozen, learned, fixed_depth (all same init/data/opt)
- Tests: 10/10 causal invariants pass (dense==plain, skip==identity, budget,
  determinism, frozen no-grad, learned updates, parity, checkpoint roundtrip)
- Mutation gate: WP-1 curated 12/12 (unchanged); router invariants are the
  causal safety net for this phase

## 5. EXPERIMENTS (pilot, 3 seeds, mean)
| Variant | Seeds | Quality (query-CE) | FLOPs | E2E latency (ms/256) | VRAM | Energy |
|---|---:|---:|---:|---:|---:|---:|
| dense | 3 | 0.00599 | 4.72e8 | see raw | tracked | EXCLUDED |
| random | 3 | 0.02008 | 2.37e8 | see raw | tracked | EXCLUDED |
| frozen | 3 | 0.00257 | 2.37e8 | see raw | tracked | EXCLUDED |
| learned | 3 | 0.00387 | 2.37e8 | see raw | tracked | EXCLUDED |
| fixed_depth | 3 | 0.00433 | 2.37e8 | see raw | tracked | EXCLUDED |

## 6. CAUSAL VERDICT
- Learned vs random: **learned better** (Δ=−0.0162, CI [−0.020,−0.014] < 0)
- Learned vs frozen: **indistinguishable** (Δ=+0.0013, CI straddles 0)
- Learned vs fixed: **indistinguishable** (Δ=−0.0005, CI straddles 0)
- Collapse status: **ROUTER_COLLAPSE** — learned policy constant [1,1,1,1,0,0,0,0], identical to fixed_depth
- Compute parity: PASS (0.03%)

## 7. PARETO VERDICT
- Status: **PARETO_NOT_SUPPORTED** (via ROUTER_COLLAPSE)
- Supported objectives: learned ≥ random (consistency beats randomness)
- Failed objectives: learned not > frozen, not > fixed-depth; no adaptivity
- Confidence: paired bootstrap 95% CIs, 3 seeds (pilot)
- Claim level: **L1** (executable contract; causal isolation achieved,
  answer negative) — NOT L3 (no learned-component causal advantage), NOT L4.

## 8. FAILURES AND DEVIATIONS
- Learned controller collapsed to a static policy — the primary scientific
  finding, not a bug (recorded, `failures/`).
- 6 deviations logged (`preregistration/deviations.jsonl`): self-contained
  block, synthetic task, positional embeddings added, difficulty calibration
  (n_pairs/lr/steps), 2-window overhead design, pynvml install. All pre-claim,
  argued, accepted.
- One analyze.py bug found & fixed post-run: budget-violation check wrongly
  included dense (all-L by design) → spurious MEASUREMENT_INVALID; corrected to
  K-configs only. Data unaffected.

## 9. NEXT DECISIVE STEP
Re-run at a BINDING budget (K=2 of 8) on a task with genuinely input-dependent
required depth, plus a per-token routing variant, to test whether adaptivity
ever beats static selection when the budget actually bites. Only if learned
then beats frozen AND fixed-depth at ≥5 seeds does WP-2 reach L3.

---
```text
BASELINE_INTEGRITY: PASS
WP1_EVIDENCE_CHAIN: PASS
WP1_OVERHEAD_GATE: PASS
WP1_ENERGY: UNAVAILABLE
WP2_IMPLEMENTATION: PASS
WP2_CONTROLS: PASS
COMPUTE_PARITY: PASS
ROUTING_CAUSALITY: NOT_SUPPORTED
PARETO_EVIDENCE: NOT_SUPPORTED
CLAIM_LEVEL: 1
NEXT_ACTION: re-run at binding budget K=2 on an input-dependent-depth task + per-token variant, >=5 seeds
```

## Definition of Done (Act §17)
NEGATIVE COMPLETION achieved: "Learned routing does not outperform matched
controls (frozen, fixed-depth); the routing hypothesis is narrowed — at this
scale/task/budget, learned *adaptive* allocation collapses to static
allocation and provides no advantage over it." This is a scientifically useful
result produced by a VALID experiment (qualified instrument, exact parity,
working controls, zero budget violations), not an invalid one.
