# WP-1 → L2 confirmatory run — PREREGISTRATION

Registered: 2026-07-16, BEFORE execution. Commit of this file precedes the run.
Protocol authority: DCSA v2.0 (`DCSA_PROTOCOL_V2.md`) + Act §4.14/§9 gate.

## Prior state (what this run may and may not change

Three exploratory runs at depth=12 exist (`WP1_INSTRUMENTATION.md` §Overhead):
CI-criterion passed 3/3; strict point-criterion (≤1.0%) passed 2/3 (canonical
run: 1.03%); verdict fail-closed `BLOCKED_BY_MEASUREMENT_OVERHEAD`. The docs
name the legitimate resolution path: a higher-power run (more cycles → tighter
CI). This document preregisters exactly ONE confirmatory run.

**Stopping rule: N = 1.** No re-runs regardless of outcome. A failed
confirmatory run is landed as a negative artifact, not retried.

## Confirmatory run specification

- Command: `scripts/instrumentation_overhead.py` with
  `--cycles 10 --warmup-steps 20 --measurement-steps 200 --seed 1234`
  (model config unchanged from canonical: depth=12, n_embd=768, n_head=6,
  seq_len=256, batch=4) → 2000 paired samples, 4× the power of each prior run.
- Environment preconditions (verified and recorded immediately before launch;
  if violated, the run is POSTPONED, never reinterpreted): zero compute
  processes on the GPU; GPU memory used ≤ 100 MiB; utilization ≤ 10%.
- Precondition snapshot at registration time: 0 compute processes, 13 MiB
  used, 8% util. Known anomaly recorded pre-run: `nvidia-smi power.draw`
  reads 749.67 W at idle — physically impossible for RTX 3050 Laptop
  (TGP ≤ 80 W); the power *rate* counter is untrusted a priori.

## Decision rule (unchanged from the earlier, stricter registration)

PASS ⇔ all three, computed by the script's existing preregistered logic:
1. median paired E2E overhead ≤ 1.0%;
2. bootstrap 95% CI upper bound ≤ 2.0%;
3. GPU-specific overhead (pooled vs bare CUDA events, cycle-averaged) ≤ 1.0%.

The τ = 1.05 (5%) figure in `DCSA_AUDIT_0002.md` §10 is **VOID for this
gate**: it was registered in ignorance of the earlier, stricter Act threshold.
Thresholds may never be loosened after data exist. The stricter rule governs.

## Outcome mapping (both directions preregistered)

- PASS → overhead gate `BLOCKED_BY_MEASUREMENT_OVERHEAD` →
  `QUALIFIED_AT_DEPTH12_SCALE`. L2 unlocks **for depth≥12-scale runs on this
  hardware class only**. The toy-scale (depth=6, ~2.2%) failure remains
  standing documentation of the scale boundary — it is not erased by a pass.
- FAIL → verdict becomes `REFUTED_AT_THIS_SCALE_ON_THIS_HW`; L2 stays closed
  on this hardware; unlocking then requires different hardware (larger model
  scale), not protocol iteration.

## Energy-liveness instrument check (separate, also preregistered)

Deviation recorded: `nvidia-ml-py` (pynvml) will be installed into `.venv`
(absent from `uv.lock`; exact version reported in results). Criteria:
1. counters readable via NVML without error;
2. `nvmlDeviceGetTotalEnergyConsumption` delta over a fixed synthetic GPU
   load window is positive, finite, monotonic;
3. physical plausibility: implied average power under load ∈ [1, 120] W and
   at idle ∈ [0.5, 50] W (RTX 3050 Laptop TGP ≤ 80 W plus margin).

Outcomes: all pass → `ENERGY_STATUS = MEASURED_LIVE (qualified)`;
unreadable → remains `NOT_MEASURED`; readable but implausible/non-monotonic →
`INSTRUMENT_INVALID` (the counter exists and lies — worse than absent, and
reported as such; no energy figure may ever be derived from an
INSTRUMENT_INVALID counter).

## What this run cannot claim even on full PASS

L2 means "metrics fit for comparison" at the qualified scale. It licenses no
statement about CWC capabilities (WP-2…WP-7 remain pre-L0), no Pareto claim,
and no energy efficiency claim (energy liveness ≠ energy-based comparison
protocol, which needs its own parity design).
