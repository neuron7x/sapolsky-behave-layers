# DGC-03 Post-Execution Integrity Note 001

Observed after the first frozen execution: the reporting helper `_metric()` charged the DGC route-envelope FLOPs to the rows labeled `FIXED_DEPTH_1` and `FIXED_DEPTH_2` because it reused `dynamic_compute()` for every mask.

This is a **baseline-reporting defect**, not a DGC decision-rule or endpoint defect:

- DGC continuation decisions, losses, and logical FLOPs are unchanged;
- `Savings_vs_depth2` for DGC was already computed against `flop_contract().fixed_depth2` directly and is unchanged;
- `DeltaQuality_vs_depth2` was already computed from exact depth-2 loss and is unchanged;
- the frozen DGC-03 verdict (`LOCAL_MODEL_30PCT_NOT_SUPPORTED`) is unchanged;
- no alpha, split, threshold, seed, row, feature, checkpoint, or metric definition is changed.

Correction: fixed-depth baselines are reported with exact `fixed_depth1` / `fixed_depth2` FLOPs and no route envelope. The scientific run is replayed only to regenerate internally consistent reporting artifacts.
