# Measurement Uncertainty and Metrology Report

## FLOPs
Accounted separately: logical, executed-kernel, profiler-supported, estimated-unsupported,
controller, routing/dispatch, memory, adaptation. Cross-checked against a profiler
(`scripts/` FLOP cross-check; `experiments/wp2_routing_v2/tests/test_flop_crosscheck.py`).
Reference gate: analytical vs profiler discrepancy ≤ 1% on unfused kernels.

## Latency (protocol)
≥50 warm-up + ≥500 measured iterations, ≥3 process launches, CUDA sync around the
interval, report p50/p90/p95/p99 + MAD, controller/dispatch/compilation separated.
Full latency sweep at scale is `NOT_MEASURED` locally (cloud).

## VRAM
weights · optimizer state · gradients · activations · KV cache · routing buffers ·
memory buffers · temporaries · peak allocated · peak reserved.

## Energy
Allowed: cumulative GPU energy counter, calibrated external meter, other validated
counter. **Forbidden:** TDP × runtime, cross-GPU extrapolation, energy claim while
`INSTRUMENT_INVALID`. On RTX 3050 this hardware is `INSTRUMENT_INVALID` → energy is
`NOT_MEASURED` and excluded from every claim.

## Reference tests
Metric reference/known-answer tests pass (`test_metrics_fix.py`,
`test_compute_parity.py`, `test_flop_crosscheck.py`). Units, measurement conditions and
uncertainty are stated with each reported number; unsupported values are marked
`NOT_MEASURED`.
