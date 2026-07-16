# Split, Contamination and Test-Access Policy

Because CWC data is synthetic and seed-determined, "splits" are disjoint seed ranges
and `mode="train"|"test"` in the generators. Even so, the discipline holds:

- Test streams use a **fixed evaluation seed** (e.g. `manual_seed(999_999)` /
  `999_983`) distinct from training seeds.
- **Test labels are never used to tune** the controller or select thresholds
  (validation only). The R3-C fix exists precisely because label-derived test capacity
  was a leak that had to be removed.
- Every confirmatory run records the eval seed in its verdict; re-examining a test
  configuration means a **new benchmark version**, not silent reuse.
- **Contamination** is structurally impossible between disjoint synthetic seed ranges,
  but any real-workload data (future) MUST add explicit contamination checks before use.
- Surface-leakage of the split is audited (`leakage_probe.py`); a benchmark a surface
  probe can classify is `BENCHMARK_INVALID_SURFACE_LEAKAGE`.
