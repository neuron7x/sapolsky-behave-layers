# WP-1 RELEASE VERDICT — reconstructed evidence bundle

Generated: 2026-07-16. Protocol: CWC Claude Fable Execution Act v1.0.0,
Phase A (evidence-chain reconstruction) + Phase B (metrology closure).
Every result below references a real file in this bundle produced by an
exact command; nothing is asserted from memory.

## Baseline integrity (Act A2) — PASS
- `git rev-parse master` = `92d63d4e8bb4df75c3b71618f31ddde2378b2bcd`
  == Act baseline_commit. Tag `wp0-fixation-2026-07-16` present. Refs
  `baseline`, `cwc-fixation`, `master` all point at the fixation commit.
- Working branch: `wp1-instrumentation`. 16 atomic commits since baseline,
  59 files changed (+6425/−36). See `commit_map.json`, `repository_manifest.json`.

## WP-1 code-quality gates (re-run fresh at this HEAD)
| Gate | Result | Evidence file | Status |
|---|---|---|---|
| Lint (ruff) | clean | (make -f Makefile.cwc verify) | VERIFIED |
| Types (mypy --strict, 20 files) | clean | (verify) | VERIFIED |
| cwc-scoped suite | 209 passed | `test_results/pytest_cwc_scoped.txt` | VERIFIED |
| Full repo suite | 257 passed / 10 skipped (FA3-conditional) | `test_results/pytest_fast.txt` | VERIFIED |
| Branch coverage | 99% (floor 95%) | `coverage/coverage.txt` | VERIFIED |
| Determinism | 8 passed | `determinism/determinism.txt` | VERIFIED |
| Mutation (curated) | 12/12 killed | `mutation/mutation.txt` | VERIFIED |

Skips are FA3-hardware-conditional (attention-fallback comparison needs
FlashAttention-3), documented — not hidden (Act §3.2 compliance).

## Metrology (Act §5, Phase B)

### Overhead gate — PASS (was BLOCKED)
Confirmatory run, preregistered N=1 stopping rule
(`docs/WP1_L2_PREREGISTRATION.md`), 4× the power of each prior exploratory run.
- Config: depth=12, n_embd=768, n_head=6, seq_len=256, batch=4 (largest that
  fits this 4 GiB GPU), CUDA, eager. 10 cycles × 200 measurement steps =
  **2000 paired samples**. Evidence: `overhead/overhead_report_confirmatory_L2.json`.

| Metric | Value | Gate | Status |
|---|---|---|---|
| median paired E2E overhead | **−0.46%** | ≤ 1.0% | PASS |
| bootstrap 95% CI (paired) | **[+0.086%, +0.306%]** | upper ≤ 2.0% | PASS |
| GPU-specific overhead (pooled vs bare CUDA events, cycle-averaged) | **−0.21%** | ≤ 1.0% | PASS |

The paired CI is entirely positive but ≤ 0.31% — i.e. the true measurement
cost is real but ~0.1–0.3% of step time, decisively under gate. The median
point estimate is slightly negative (COUNTERS ≈ OFF within thermal noise).
Absolute meter cost is not hidden: it is sub-millisecond against a ~52.5 ms
step (off_p50 = 52.57 ms, counters_p50 = 52.33 ms).

**DEVIATION (recorded):** the existing qualified script uses a 2-window
alternating design (OFF, COUNTERS × 10 cycles) rather than the Act B4
4-window palindrome (OFF→COUNTERS→COUNTERS→OFF). Alternation across 10 cycles
balances thermal/clock drift across arms; the palindrome balances it within a
cycle. Both are valid order-controls; the ~0.1–0.3% result is far from the
1% threshold, so the design difference cannot flip the verdict. Logged in
`../../experiments/wp2_routing_v1/deviations.jsonl` when Phase C opens.

### Energy — INSTRUMENT_INVALID → ENERGY_METRICS = NON_CLAIMABLE
Preregistered liveness probe (`energy/energy_liveness_probe.json`):
- NVML counters readable, deltas positive/finite/monotonic (both idle & load).
- **Physical plausibility FAILS:** load window implied 160.8 W avg power via
  `nvmlDeviceGetTotalEnergyConsumption`, but RTX 3050 Laptop TGP ≤ 80 W; the
  simultaneous instantaneous rate read 79.8 W (at the cap). The energy counter
  over-reads by ~2×; idle cross-check ~4.8× (16.6 W counter vs 3.4 W rate).
- Fourth independent manifestation of untrusted power telemetry on this host
  (749.67 W idle `power.draw` recorded twice + a prior-session anomaly).

Per Act B6/B7: TDP fallback is forbidden, so **ENERGY_VALIDATION =
UNAVAILABLE**, energy metrics NON_CLAIMABLE. This does NOT block the routing
experiment on FLOPs/VRAM/latency.

## Gate A / Gate B verdict
```text
BASELINE_INTEGRITY            = PASS
WP1_EVIDENCE_CHAIN (Gate A)   = PASS  (bundle references real files, checksums valid)
WP1_OVERHEAD_GATE             = PASS
WP1_ENERGY                    = UNAVAILABLE (INSTRUMENT_INVALID, non-claimable)
WP1_METROLOGY (Gate B)        = PASS_WITH_ENERGY_EXCLUDED
```
CLAIM_LEVEL for WP-1: **L2 (MEASUREMENT VALIDITY)** at depth-12 scale on this
hardware class, energy dimension excluded. Unblocks Phase C (WP-2
preregistration). No architectural/Pareto/efficiency claim is licensed.
